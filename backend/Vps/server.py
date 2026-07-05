# server.py — DRAGO Prediction Engine (ADVANCED SELF-LEARNING v2.0)
# ──────────────────────────────────────────────────────────────────────────
# NAYA FEATURE (v2.0):
#   • PREDICTION HISTORY MEMORY: Har prediction ka full record rakha jata hai
#     (situation → prediction → result → sahi/galat)
#   • MISTAKE AVOIDANCE: Agar same situation pehle galti kari thi, to engine
#     wahi galti dobara nahi karega — opposite prefer karega
#   • SITUATION FINGERPRINT: Context (last N results + loss level + streak)
#     ek unique "situation ID" banta hai — same situation = same memory
#   • CONFIDENCE CALIBRATION: History se actual accuracy nikaali jati hai,
#     overconfident predictions auto-correct hoti hain
#   • STREAK DETECTION: Agar ek side ka streak hai, engine us pe dhyan deta hai
#
# 3 streams:
#     • TRX-1m    (TrxWinGo 1 minute)
#     • Wingo-1m  (WinGo 1 minute)
#     • Wingo-30s (WinGo 30 second)
#
# Har stream ke 2 servers:
#     • NOVA X  -> Color (GREEN / RED)
#     • PRIME X -> Size  (BIG / SMALL)
# ──────────────────────────────────────────────────────────────────────────

import os
import math
import time
import json
import logging
import threading
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, HTTPException

logger = logging.getLogger("drago.engine")

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════
MONGO_URI      = os.getenv("MONGO_URI", "mongodb+srv://krishnavishwas011_db_user:OgktWrNR3KGzo2rj@datacenter.xuicoag.mongodb.net/ai_predictions?retryWrites=true&w=majority&appName=Datacenter")
ENGINE_DB_NAME = os.getenv("ENGINE_DB_NAME", "drago_final")

STREAMS_CONFIG = {
    "trx_1m": {
        "label":    "TRX-1m",
        "prefix":   "trx1m",
        "api":      "https://draw.ar-lottery01.com/TrxWinGo/TrxWinGo_1M/GetHistoryIssuePage.json",
        "poll_sec": 3,
    },
    "wingo_1m": {
        "label":    "Wingo-1m",
        "prefix":   "wingo1m",
        "api":      "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json",
        "poll_sec": 3,
    },
    "wingo_30s": {
        "label":    "Wingo-30s",
        "prefix":   "wingo30s",
        "api":      "https://draw.ar-lottery01.com/WinGo/WinGo_30S/GetHistoryIssuePage.json",
        "poll_sec": 3,
    },
}

ROUTE_MAP = {
    ("trx",   "1m"):  "trx_1m",
    ("wingo", "1m"):  "wingo_1m",
    ("wingo", "30s"): "wingo_30s",
}

# Learning config
CONTEXT_LENGTHS  = [1, 2, 3, 4, 5]   # 5 tak context (zyada patterns)
MIN_OBSERVATIONS = 2
DECAY            = 0.90               # pehle se faster fade (0.96 → 0.90)
EWMA_ALPHA       = 0.40               # galti pe faster react (0.30 → 0.40)
CONF_FLOOR       = 52
CONF_CAP         = 91

# ── NAYE CONSTANTS (v2.0) ─────────────────────────────────────────────────
MISTAKE_MEMORY_SIZE  = 500   # kitni galtiyan yaad rakho
PRED_HISTORY_SIZE    = 1000  # kitni predictions yaad rakho
MISTAKE_PENALTY      = 0.55  # galat situation me us letter ka prob kitna girae (0-1)
MISTAKE_MIN_COUNT    = 1     # kitni baar galti hone par avoid karo (1 = immediate)
STREAK_THRESHOLD     = 3     # kitni consecutive same letters = streak
SITUATION_WINDOW     = 6     # situation fingerprint ke liye last N letters

# ═══════════════════════════════════════════════════════════════════════════
# MONGODB
# ═══════════════════════════════════════════════════════════════════════════
mongo_db = None
mongo_ok = False
if MONGO_URI and MONGO_URI != "PASTE_YOUR_MONGO_URI_HERE":
    try:
        from pymongo import MongoClient
        _mc = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        _mc.admin.command("ping")
        mongo_db = _mc[ENGINE_DB_NAME]
        mongo_ok = True
        logger.info("✅ [engine] MongoDB connected")
    except Exception as e:
        logger.error(f"❌ [engine] MongoDB connect failed: {e} — running in-memory only")
else:
    logger.warning("⚠️ [engine] MONGO_URI not set — running in-memory only")


# ═══════════════════════════════════════════════════════════════════════════
# GAME RULES
# ═══════════════════════════════════════════════════════════════════════════
def get_size(n: int) -> str:
    return "BIG" if int(n) >= 5 else "SMALL"

def get_color(n: int) -> str:
    n = int(n)
    if n in (1, 3, 7, 9): return "GREEN"
    if n in (2, 4, 6, 8): return "RED"
    if n == 5:             return "GREEN"
    if n == 0:             return "RED"
    return "?"

def color_letter(n: int) -> str:
    return "G" if get_color(n) == "GREEN" else "R"

def size_letter(n: int) -> str:
    return "B" if get_size(n) == "BIG" else "S"

def is_win_color(pred: str, actual_n: int) -> bool:
    return str(pred).upper().strip() == get_color(int(actual_n))

def is_win_size(pred: str, actual_n: int) -> bool:
    return str(pred).upper().strip() == get_size(int(actual_n))


# ═══════════════════════════════════════════════════════════════════════════
# LOSS-LEVEL TRACKER  (L1🟢 → L4🔴)
# ═══════════════════════════════════════════════════════════════════════════
class LossLevel:
    MAX_LEVEL = 4
    STRATEGY = {
        1: {"switch_bias": 0.00, "badge": "🟢L1", "desc": "NORMAL"},
        2: {"switch_bias": 0.25, "badge": "🟡L2", "desc": "CAREFUL"},   # stronger
        3: {"switch_bias": 0.50, "badge": "🟠L3", "desc": "ALERT"},     # stronger
        4: {"switch_bias": 0.80, "badge": "🔴L4", "desc": "RECOVER"},   # much stronger
    }

    def __init__(self):
        self.level         = 1
        self.consec_losses = 0
        self.total_wins    = 0
        self.total_losses  = 0

    def on_result(self, was_correct: bool):
        if was_correct:
            self.total_wins    += 1
            self.consec_losses  = 0
            self.level          = 1
        else:
            self.total_losses  += 1
            self.consec_losses += 1
            self.level          = min(self.consec_losses + 1, self.MAX_LEVEL)

    def strategy(self):
        return self.STRATEGY[self.level]

    def badge(self):
        return self.STRATEGY[self.level]["badge"]

    def to_dict(self):
        return {
            "level":         self.level,
            "consec_losses": self.consec_losses,
            "total_wins":    self.total_wins,
            "total_losses":  self.total_losses,
        }

    def from_dict(self, d):
        self.consec_losses = d.get("consec_losses", 0)
        self.total_wins    = d.get("total_wins", 0)
        self.total_losses  = d.get("total_losses", 0)
        self.level = 1 if self.consec_losses == 0 else min(self.consec_losses + 1, self.MAX_LEVEL)


# ═══════════════════════════════════════════════════════════════════════════
# ★ NAYA: PREDICTION HISTORY MEMORY  (v2.0 ka core feature)
#
# Har prediction ko uski "situation" ke saath store karta hai:
#   situation_key  = hash(last_N_letters + loss_level + streak_info)
#   prediction     = jo letter predict kiya
#   result         = actual letter jo aaya
#   was_correct    = sahi/galat
#
# Future mein same situation aane par:
#   → Agar pehle galti ki thi → woh letter avoid karo
#   → Agar pehle sahi tha     → woh letter prefer karo
# ═══════════════════════════════════════════════════════════════════════════
class PredictionHistoryMemory:
    """
    Situation → {letter → {wins, losses, accuracy_ewma}} yaad rakhta hai.
    Situation = (recent_pattern + loss_level + streak).
    """

    def __init__(self):
        # situation_key -> {letter -> {w, l, acc, plays}}
        self.sit_memory: dict[str, dict[str, dict]] = defaultdict(
            lambda: defaultdict(lambda: {"w": 0, "l": 0, "acc": 0.5, "plays": 0})
        )
        # Full prediction log (PRED_HISTORY_SIZE recent)
        self.pred_log: deque = deque(maxlen=PRED_HISTORY_SIZE)
        # Galtiyon ka compact index: situation_key -> {letter -> count}
        self.mistake_index: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def make_situation_key(self, history: deque, loss_level: int) -> str:
        """
        Unique situation fingerprint banao:
          - Last SITUATION_WINDOW letters (e.g., "GRGRBS")
          - Current loss level (1-4)
          - Streak info (kitni consecutive same letters)
        """
        recent = list(history)[-SITUATION_WINDOW:] if len(history) >= 1 else []
        pattern = "".join(recent)

        # streak calculate karo
        streak = 0
        if recent:
            last = recent[-1]
            for ch in reversed(recent):
                if ch == last:
                    streak += 1
                else:
                    break
        streak_tag = f"S{min(streak, 5)}"  # S1..S5

        raw = f"{pattern}|L{loss_level}|{streak_tag}"
        # short hash taaki keys compact rahe
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def record_result(self, situation_key: str, pred_letter: str,
                      actual_letter: str, period: str):
        """Prediction ka result record karo — memory update karo."""
        correct = (pred_letter == actual_letter)

        entry = self.sit_memory[situation_key][pred_letter]
        if correct:
            entry["w"] += 1
        else:
            entry["l"]  += 1
            # Galti index me add karo
            self.mistake_index[situation_key][pred_letter] += 1

        entry["plays"] += 1
        # EWMA accuracy: galti pe jaldi girti hai
        entry["acc"] = (1 - EWMA_ALPHA) * entry["acc"] + EWMA_ALPHA * (1.0 if correct else 0.0)

        # Full log
        self.pred_log.append({
            "period":      period,
            "sit_key":     situation_key,
            "pred":        pred_letter,
            "actual":      actual_letter,
            "correct":     correct,
            "ts":          datetime.now(timezone.utc).isoformat(),
        })

    def get_situation_bias(self, situation_key: str, letter: str) -> float:
        """
        Is situation me is letter ke liye historical bias nikaalo.
        Returns: float (-1.0 to +1.0)
          Positive = is situation me ye letter historically sahi raha
          Negative = is situation me ye letter galat raha (avoid karo)
        """
        entry = self.sit_memory.get(situation_key, {}).get(letter)
        if not entry or entry["plays"] < MISTAKE_MIN_COUNT:
            return 0.0  # koi data nahi → neutral

        acc  = entry["acc"]   # 0..1
        bias = (acc - 0.5) * 2.0  # -1 to +1
        return bias

    def was_mistake_here(self, situation_key: str, letter: str) -> bool:
        """Is situation + letter combination me pehle galti hui thi?"""
        return self.mistake_index.get(situation_key, {}).get(letter, 0) >= MISTAKE_MIN_COUNT

    def get_mistake_count(self, situation_key: str, letter: str) -> int:
        return self.mistake_index.get(situation_key, {}).get(letter, 0)

    def to_dict(self) -> dict:
        return {
            "sit_memory":    {k: dict(v) for k, v in self.sit_memory.items()},
            "mistake_index": {k: dict(v) for k, v in self.mistake_index.items()},
            "pred_log":      list(self.pred_log),
        }

    def from_dict(self, d: dict):
        for k, v in d.get("sit_memory", {}).items():
            for letter, stats in v.items():
                self.sit_memory[k][letter] = stats
        for k, v in d.get("mistake_index", {}).items():
            for letter, cnt in v.items():
                self.mistake_index[k][letter] = cnt
        for entry in d.get("pred_log", []):
            self.pred_log.append(entry)


# ═══════════════════════════════════════════════════════════════════════════
# STREAK DETECTOR
# ═══════════════════════════════════════════════════════════════════════════
class StreakDetector:
    """Consecutive same letters ka streak track karta hai."""

    def __init__(self):
        self.current_letter = None
        self.length         = 0
        self.max_seen       = 0

    def update(self, letter: str):
        if letter == self.current_letter:
            self.length += 1
        else:
            self.current_letter = letter
            self.length         = 1
        self.max_seen = max(self.max_seen, self.length)

    def get_streak_letter(self) -> str | None:
        """Agar STREAK_THRESHOLD ya zyada streak chal raha hai to letter return karo."""
        if self.length >= STREAK_THRESHOLD:
            return self.current_letter
        return None

    def streak_length(self) -> int:
        return self.length

    def to_dict(self):
        return {"letter": self.current_letter, "length": self.length, "max": self.max_seen}

    def from_dict(self, d):
        self.current_letter = d.get("letter")
        self.length         = d.get("length", 0)
        self.max_seen       = d.get("max", 0)


# ═══════════════════════════════════════════════════════════════════════════
# SELF-LEARNING SERVER  (NOVA X / PRIME X) — v2.0
# ═══════════════════════════════════════════════════════════════════════════
class SelfLearningServer:
    def __init__(self, stream_id: str, target: str):
        self.stream_id = stream_id
        self.target    = target
        self.name      = "NOVA_X" if target == "color" else "PRIME_X"
        self.sid       = f"{stream_id}_{self.name}"

        # Core pattern memory (unchanged from v1, improved params)
        self.mem = defaultdict(lambda: defaultdict(
            lambda: {"w": 0, "l": 0, "total": 0, "wt": 0.0, "acc": 0.5, "plays": 0}
        ))

        self.history   = deque(maxlen=500)
        self.wins      = 0
        self.total     = 0
        self.loss      = LossLevel()

        # ★ v2.0: Naye components
        self.pred_history = PredictionHistoryMemory()   # galtiyan yaad rakho
        self.streak       = StreakDetector()             # streaks track karo
        self.last_pred_letter   = None   # last prediction letter (switch bias ke liye)
        self.last_situation_key = None   # last prediction ki situation

        # Pending prediction
        self.pending    = None
        self.last_period = None

    # ── letter helpers ────────────────────────────────────────────────
    def _letter(self, n: int) -> str:
        return color_letter(n) if self.target == "color" else size_letter(n)

    def _label(self, letter: str) -> str:
        if self.target == "color":
            return "GREEN" if letter == "G" else "RED"
        return "BIG" if letter == "B" else "SMALL"

    def _is_win(self, label: str, n: int) -> bool:
        return is_win_color(label, n) if self.target == "color" else is_win_size(label, n)

    def _opposite(self, letter: str) -> str:
        if self.target == "color":
            return "R" if letter == "G" else "G"
        return "S" if letter == "B" else "B"

    def _all_letters(self):
        if self.target == "color": return ["G", "R"]
        return ["B", "S"]

    # ── 1) result check ───────────────────────────────────────────────
    def _check_pending(self, actual_n: int, actual_letter: str):
        if not self.pending:
            return None
        p       = self.pending
        correct = self._is_win(p["label"], actual_n)

        self.total += 1
        if correct:
            self.wins += 1

        # Core memory update
        entry = self.mem[p["pattern"]][p["pred_letter"]]
        entry["w" if correct else "l"] += 1
        entry["plays"] += 1
        entry["acc"] = (1 - EWMA_ALPHA) * entry["acc"] + EWMA_ALPHA * (1.0 if correct else 0.0)

        # ★ v2.0: Prediction history memory update
        if self.last_situation_key:
            self.pred_history.record_result(
                situation_key = self.last_situation_key,
                pred_letter   = p["pred_letter"],
                actual_letter = actual_letter,
                period        = p["period"],
            )

        # Loss level update
        self.loss.on_result(correct)
        self.pending = None
        return correct

    # ── 2) learn ──────────────────────────────────────────────────────
    def _learn(self, actual_letter: str):
        for L in CONTEXT_LENGTHS:
            if len(self.history) >= L:
                pattern = "".join(list(self.history)[-L:])
                bucket  = self.mem[pattern]
                for st in bucket.values():
                    st["wt"] *= DECAY
                cell = bucket[actual_letter]
                cell["total"] += 1
                cell["wt"]    += 1.0

    # ── 3) streak-aware opposite ──────────────────────────────────────
    def _get_switch_target(self) -> str:
        """
        Kaun sa letter prefer karna chahiye switch ke time:
        1. Agar long streak chal rahi hai → streak letter ka opposite
        2. Warna last prediction ka opposite (galti cover karo)
        3. Fallback: last history letter ka opposite
        """
        streak_letter = self.streak.get_streak_letter()
        if streak_letter and self.streak.streak_length() >= STREAK_THRESHOLD:
            return self._opposite(streak_letter)

        if self.last_pred_letter:
            return self._opposite(self.last_pred_letter)

        if self.history:
            return self._opposite(self.history[-1])

        return "G" if self.target == "color" else "B"

    # ── 4) MAIN PREDICTION (v2.0 — situation-aware) ───────────────────
    def _predict_next(self):
        strat        = self.loss.strategy()
        switch_bias  = strat["switch_bias"]
        switch_target = self._get_switch_target()

        # ★ v2.0: Current situation ka fingerprint
        sit_key = self.pred_history.make_situation_key(self.history, self.loss.level)

        # L4: Hard force opposite (memory ignore)
        if self.loss.level == 4:
            letter = switch_target
            conf   = min(CONF_FLOOR + 15, CONF_CAP)
            # Phir bhi check karo: kya is situation me switch_target ne bhi galti ki thi?
            if self.pred_history.was_mistake_here(sit_key, letter):
                # Dono galat rahe hain → phir bhi switch_target lao (kam bura option)
                conf = CONF_FLOOR
            self.last_situation_key = sit_key
            return {
                "pattern_len": 0, "pattern": "L4_FORCE",
                "pred_letter": letter, "label": self._label(letter),
                "conf": conf, "acc": float(conf),
                "sit_key": sit_key, "method": "L4_FORCE",
            }

        best       = None
        best_score = -999.0

        for L in CONTEXT_LENGTHS:
            if len(self.history) < L:
                continue
            pattern = "".join(list(self.history)[-L:])
            counts  = self.mem.get(pattern)
            if not counts:
                continue

            wt_all = sum(s["wt"] for s in counts.values()) or 1.0

            for letter, s in counts.items():
                if s["total"] < MIN_OBSERVATIONS:
                    continue

                freq     = s["wt"] / wt_all
                acc_ewma = s["acc"]
                plays    = s["plays"]

                w_acc = min(plays, 10) / 10.0
                prob  = (1 - w_acc) * freq + w_acc * (0.5 * freq + 0.5 * acc_ewma)

                # ★ v2.0: Situation history bias apply karo
                sit_bias = self.pred_history.get_situation_bias(sit_key, letter)
                # sit_bias: -1 (always wrong here) to +1 (always right here)
                prob += sit_bias * 0.30   # 30% weight to situation history

                # ★ v2.0: Mistake penalty — is situation me ye letter galat raha
                mistake_count = self.pred_history.get_mistake_count(sit_key, letter)
                if mistake_count >= MISTAKE_MIN_COUNT:
                    penalty = MISTAKE_PENALTY * min(mistake_count, 5) / 5.0
                    prob -= penalty
                    logger.debug(
                        f"[engine] {self.sid}: situation {sit_key} "
                        f"letter={letter} mistake_count={mistake_count} penalty={penalty:.2f}"
                    )

                # Switch bias (loss level se)
                if letter == switch_target:
                    prob += switch_bias
                else:
                    prob -= switch_bias * 0.5

                # ★ v2.0: Streak bias — agar long streak chal rahi hai
                streak_letter = self.streak.get_streak_letter()
                if streak_letter:
                    if letter == self._opposite(streak_letter):
                        # Streak break hone ki possibility → prefer opposite
                        prob += 0.15 * min(self.streak.streak_length() / 5.0, 1.0)
                    elif letter == streak_letter:
                        # Streak continue kar raha letter → thoda penalize
                        prob -= 0.10

                prob  = max(0.02, min(prob, 0.98))
                score = prob * math.log(s["wt"] + 1.5) * (1 + L * 0.07)

                if score > best_score:
                    best_score = score
                    conf = int(max(CONF_FLOOR, min(prob * 100, CONF_CAP)))
                    best = {
                        "pattern_len": L,
                        "pattern":     pattern,
                        "pred_letter": letter,
                        "label":       self._label(letter),
                        "conf":        conf,
                        "acc":         round(prob * 100, 1),
                        "sit_key":     sit_key,
                        "method":      "PATTERN",
                    }

        # Fallback
        if best is None and len(self.history) >= 1:
            best = self._fallback_predict(switch_bias, switch_target, sit_key)

        self.last_situation_key = sit_key
        return best

    # ── Fallback prediction ───────────────────────────────────────────
    def _fallback_predict(self, switch_bias: float, switch_target: str, sit_key: str):
        recent = list(self.history)[-20:]
        a      = "G" if self.target == "color" else "B"
        b      = "R" if self.target == "color" else "S"
        ca, cb = recent.count(a), recent.count(b)

        probs = {a: ca / (len(recent) or 1), b: cb / (len(recent) or 1)}

        # Situation history bias apply karo
        for letter in [a, b]:
            sit_bias = self.pred_history.get_situation_bias(sit_key, letter)
            probs[letter] = max(0.02, probs[letter] + sit_bias * 0.3)

            # Mistake penalty
            mistakes = self.pred_history.get_mistake_count(sit_key, letter)
            if mistakes >= MISTAKE_MIN_COUNT:
                probs[letter] = max(0.02, probs[letter] - MISTAKE_PENALTY * 0.5)

        # Switch bias
        if switch_target == a:
            probs[a] = min(0.98, probs[a] + switch_bias * 0.5)
        else:
            probs[b] = min(0.98, probs[b] + switch_bias * 0.5)

        letter = a if probs[a] >= probs[b] else b
        prob   = probs[letter]
        conf   = int(max(CONF_FLOOR, min(prob * 100, CONF_CAP)))

        return {
            "pattern_len": 0, "pattern": "*_FALLBACK",
            "pred_letter": letter, "label": self._label(letter),
            "conf": conf, "acc": round(prob * 100, 1),
            "sit_key": sit_key, "method": "FALLBACK",
        }

    # ── MAIN: naya result ─────────────────────────────────────────────
    def on_new_result(self, period: str, number: int, learn_only: bool = False):
        actual_letter = self._letter(number)

        if not learn_only:
            self._check_pending(number, actual_letter)   # result check + history update

        self._learn(actual_letter)         # pattern memory update
        self.streak.update(actual_letter)  # ★ streak update
        self.history.append(actual_letter)
        self.last_period = period

        if learn_only:
            return None

        nxt = self._predict_next()
        next_period = self._next_period(period)

        if nxt:
            self.last_pred_letter = nxt["pred_letter"]   # ★ save for switch
            self.pending = {**nxt, "level": self.loss.level, "period": next_period}
        else:
            self.pending = None

        self._save_latest(next_period)
        self._save_state()
        return self.pending

    @staticmethod
    def _next_period(period: str) -> str:
        try:
            return str(int(period) + 1)
        except Exception:
            return period

    # ── Latest payload ────────────────────────────────────────────────
    def latest_payload(self, next_period: str):
        strat = self.loss.strategy()
        wr    = round(self.wins / self.total * 100, 1) if self.total else 0.0

        # ★ v2.0: Mistake stats include karo
        sit_key  = self.pred_history.make_situation_key(self.history, self.loss.level)
        mistakes = {}
        for letter in self._all_letters():
            mistakes[letter] = self.pred_history.get_mistake_count(sit_key, letter)

        total_preds   = len(self.pred_history.pred_log)
        total_correct = sum(1 for p in self.pred_history.pred_log if p["correct"])
        hist_accuracy = round(total_correct / total_preds * 100, 1) if total_preds else 0.0

        if self.pending:
            return {
                "stream":         self.stream_id,
                "server":         self.name,
                "target":         self.target,
                "period":         self.pending["period"],
                "prediction":     self.pending["label"],
                "confidence":     self.pending["conf"],
                "accuracy":       self.pending.get("acc", 0),
                "method":         self.pending.get("method", "PATTERN"),
                "level":          self.loss.level,
                "badge":          self.loss.badge(),
                "level_desc":     strat["desc"],
                "win_rate":       wr,
                "wins":           self.wins,
                "total":          self.total,
                "history_accuracy": hist_accuracy,
                "total_predictions": total_preds,
                "current_streak": self.streak.streak_length(),
                "streak_letter":  self.streak.current_letter,
                "situation_key":  sit_key,
                "status":         "READY",
                "updated_at":     datetime.now(timezone.utc).isoformat(),
            }
        return {
            "stream":         self.stream_id,
            "server":         self.name,
            "target":         self.target,
            "period":         next_period,
            "prediction":     "WAIT",
            "confidence":     0,
            "accuracy":       0,
            "method":         "NONE",
            "level":          self.loss.level,
            "badge":          self.loss.badge(),
            "level_desc":     strat["desc"],
            "win_rate":       wr,
            "wins":           self.wins,
            "total":          self.total,
            "history_accuracy": hist_accuracy,
            "total_predictions": total_preds,
            "current_streak": self.streak.streak_length(),
            "streak_letter":  self.streak.current_letter,
            "situation_key":  sit_key,
            "status":         "SKIP",
            "updated_at":     datetime.now(timezone.utc).isoformat(),
        }

    # ── MongoDB: save latest ──────────────────────────────────────────
    def _save_latest(self, next_period: str):
        if not mongo_ok:
            return
        prefix = STREAMS_CONFIG[self.stream_id]["prefix"]
        doc    = self.latest_payload(next_period)
        doc["_id"] = f"{prefix}_{self.target}_latest"
        try:
            mongo_db["latest_predictions"].replace_one({"_id": doc["_id"]}, doc, upsert=True)
            mongo_db["prediction_history"].insert_one({
                **{k: v for k, v in doc.items() if k != "_id"},
                "saved_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.error(f"[engine] save_latest {self.sid}: {e}")

    # ── MongoDB: save full state ──────────────────────────────────────
    def _save_state(self):
        if not mongo_ok:
            return
        try:
            pred_hist_dict = self.pred_history.to_dict()
            # pred_log ke last 200 hi save karo (space save)
            pred_hist_dict["pred_log"] = pred_hist_dict["pred_log"][-200:]

            mongo_db["engine_state"].replace_one(
                {"_id": self.sid},
                {
                    "_id":       self.sid,
                    "stream_id": self.stream_id,
                    "target":    self.target,
                    "wins":      self.wins,
                    "total":     self.total,
                    "loss":      self.loss.to_dict(),
                    "streak":    self.streak.to_dict(),
                    "last_period":       self.last_period,
                    "last_pred_letter":  self.last_pred_letter,
                    "pred_history":      pred_hist_dict,   # ★ save
                    "mem": [
                        {"p": pat, "n": nl, "w": s["w"], "l": s["l"], "t": s["total"],
                         "wt": round(s["wt"], 4), "acc": round(s["acc"], 4), "pl": s["plays"]}
                        for pat, vals in self.mem.items()
                        for nl, s in vals.items()
                        if s["total"] > 0
                    ],
                    "history": list(self.history),
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"[engine] save_state {self.sid}: {e}")

    # ── MongoDB: restore state ────────────────────────────────────────
    def load_state(self):
        if not mongo_ok:
            return
        try:
            doc = mongo_db["engine_state"].find_one({"_id": self.sid})
            if not doc:
                return
            self.wins             = doc.get("wins", 0)
            self.total            = doc.get("total", 0)
            self.last_pred_letter = doc.get("last_pred_letter")
            self.loss.from_dict(doc.get("loss", {}))
            self.streak.from_dict(doc.get("streak", {}))

            for h in doc.get("history", []):
                self.history.append(h)

            for row in doc.get("mem", []):
                self.mem[row["p"]][row["n"]] = {
                    "w": row.get("w", 0), "l": row.get("l", 0),
                    "total": row.get("t", 0),
                    "wt": row.get("wt", float(row.get("t", 0))),
                    "acc": row.get("acc", 0.5),
                    "plays": row.get("pl", 0),
                }

            # ★ v2.0: Prediction history restore
            ph_data = doc.get("pred_history", {})
            if ph_data:
                self.pred_history.from_dict(ph_data)

            logger.info(
                f"[engine] state restored: {self.sid} "
                f"(hist={len(self.history)}, "
                f"pred_log={len(self.pred_history.pred_log)}, "
                f"situations={len(self.pred_history.sit_memory)})"
            )
        except Exception as e:
            logger.error(f"[engine] load_state {self.sid}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# STREAM
# ═══════════════════════════════════════════════════════════════════════════
class Stream:
    def __init__(self, stream_id: str):
        self.stream_id    = stream_id
        self.cfg          = STREAMS_CONFIG[stream_id]
        self.api          = self.cfg["api"]
        self.poll_sec     = self.cfg["poll_sec"]
        self.color        = SelfLearningServer(stream_id, "color")
        self.size         = SelfLearningServer(stream_id, "size")
        self.last_period  = None
        self._bootstrapped = False
        self.results      = deque(maxlen=300)

    def _record_result(self, period: str, number: int):
        if self.results and self.results[-1]["period"] == period:
            return
        self.results.append({"period": period, "number": int(number)})

    def _fetch(self):
        try:
            r = requests.get(self.api, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return []
            d   = r.json()
            lst = (d.get("data") or {}).get("list") or []
            out = []
            for rec in lst:
                period = str(rec.get("issueNumber", "")).strip()
                num    = rec.get("number")
                if period and num is not None:
                    try:
                        out.append({"period": period, "number": int(num)})
                    except Exception:
                        continue
            out.sort(key=lambda x: x["period"])
            return out
        except Exception as e:
            logger.warning(f"[engine] fetch {self.stream_id}: {e}")
            return []

    def _bootstrap(self, records):
        self.color.load_state()
        self.size.load_state()
        seen = self.color.last_period
        for rec in records:
            self._record_result(rec["period"], rec["number"])
            if seen and rec["period"] <= seen:
                continue
            self.color.on_new_result(rec["period"], rec["number"], learn_only=True)
            self.size.on_new_result(rec["period"], rec["number"],  learn_only=True)
            self.last_period = rec["period"]
        self._bootstrapped = True
        logger.info(f"[engine] {self.cfg['label']} bootstrapped @ period {self.last_period}")

    def tick(self):
        records = self._fetch()
        if not records:
            return
        if not self._bootstrapped:
            self._bootstrap(records)
            return
        for rec in records:
            if self.last_period and rec["period"] <= self.last_period:
                continue
            self._record_result(rec["period"], rec["number"])
            self.color.on_new_result(rec["period"], rec["number"])
            self.size.on_new_result(rec["period"], rec["number"])
            self.last_period = rec["period"]
            logger.info(
                f"[engine] {self.cfg['label']} result {rec['period']} → {rec['number']} "
                f"| NOVA {self.color.loss.badge()} streak={self.color.streak.length} "
                f"| PRIME {self.size.loss.badge()} streak={self.size.streak.length}"
            )

    def run_loop(self):
        logger.info(f"🚀 [engine] stream started: {self.cfg['label']}")
        while True:
            try:
                self.tick()
            except Exception as e:
                logger.error(f"[engine] {self.stream_id} loop error: {e}")
            time.sleep(self.poll_sec)


# ═══════════════════════════════════════════════════════════════════════════
# ENGINE BOOT
# ═══════════════════════════════════════════════════════════════════════════
STREAMS: dict[str, Stream] = {}
_started    = False
_start_lock = threading.Lock()

def start_prediction_engine():
    global _started
    with _start_lock:
        if _started:
            logger.info("[engine] already started — skipping")
            return
        for sid in STREAMS_CONFIG:
            STREAMS[sid] = Stream(sid)
            threading.Thread(
                target=STREAMS[sid].run_loop,
                daemon=True,
                name=f"engine-{sid}",
            ).start()
        _started = True
        logger.info("✅ [engine] all 3 prediction streams started (v2.0)")


# ═══════════════════════════════════════════════════════════════════════════
# PUBLIC HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def resolve_stream(game: str, tf: str) -> str | None:
    return ROUTE_MAP.get((str(game).lower().strip(), str(tf).lower().strip()))

def _read_latest(stream_id: str, target: str):
    st = STREAMS.get(stream_id)
    if st:
        srv = st.color if target == "color" else st.size
        nxt = srv._next_period(srv.last_period) if srv.last_period else ""
        return srv.latest_payload(nxt)
    if mongo_ok:
        prefix = STREAMS_CONFIG[stream_id]["prefix"]
        doc    = mongo_db["latest_predictions"].find_one({"_id": f"{prefix}_{target}_latest"})
        if doc:
            doc.pop("_id", None)
            return doc
    raise HTTPException(503, "Prediction engine not ready yet.")

def read_prediction(game: str, tf: str, target: str) -> dict:
    target = str(target).lower().strip()
    if target not in ("color", "size"):
        raise HTTPException(400, "target must be 'color' or 'size'")
    stream_id = resolve_stream(game, tf)
    if not stream_id:
        raise HTTPException(404, "Unknown game/timeframe. Use trx/1m, wingo/1m, wingo/30s.")
    return _read_latest(stream_id, target)

def read_both(game: str, tf: str) -> dict:
    stream_id = resolve_stream(game, tf)
    if not stream_id:
        raise HTTPException(404, "Unknown game/timeframe. Use trx/1m, wingo/1m, wingo/30s.")
    return {
        "stream": stream_id,
        "color":  _read_latest(stream_id, "color"),
        "size":   _read_latest(stream_id, "size"),
    }

def read_results(game: str, tf: str, limit: int = 200) -> dict:
    stream_id = resolve_stream(game, tf)
    if not stream_id:
        raise HTTPException(404, "Unknown game/timeframe.")
    st = STREAMS.get(stream_id)
    if not st or not st.results:
        raise HTTPException(503, "Result engine not ready yet.")
    try:
        limit = max(1, min(int(limit), 300))
    except Exception:
        limit = 200
    items = list(st.results)[-limit:]
    return {"stream": stream_id, "count": len(items), "results": items,
            "last_period": st.last_period}

def read_latest_result(game: str, tf: str) -> dict:
    stream_id = resolve_stream(game, tf)
    if not stream_id:
        raise HTTPException(404, "Unknown game/timeframe.")
    st = STREAMS.get(stream_id)
    if not st or not st.results:
        raise HTTPException(503, "Result engine not ready yet.")
    latest     = st.results[-1]
    next_period = str(int(latest["period"]) + 1) if latest["period"].isdigit() else latest["period"]
    return {"stream": stream_id, "period": latest["period"],
            "number": latest["number"], "next_period": next_period}

def engine_status_payload() -> dict:
    """Saare streams ka health + v2.0 stats."""
    out = {"mongo": mongo_ok, "version": "2.0", "streams": {}}
    for sid, st in STREAMS.items():
        nova  = st.color
        prime = st.size

        nova_hist  = len(nova.pred_history.pred_log)
        prime_hist = len(prime.pred_history.pred_log)
        nova_sits  = len(nova.pred_history.sit_memory)
        prime_sits = len(prime.pred_history.sit_memory)

        out["streams"][sid] = {
            "label":       st.cfg["label"],
            "last_period": st.last_period,
            "bootstrapped":st._bootstrapped,
            "results":     len(st.results),
            "nova": {
                "badge":          nova.loss.badge(),
                "win_rate":       round(nova.wins / nova.total * 100, 1) if nova.total else 0,
                "streak":         nova.streak.streak_length(),
                "streak_letter":  nova.streak.current_letter,
                "pred_logged":    nova_hist,
                "situations_learned": nova_sits,
            },
            "prime": {
                "badge":          prime.loss.badge(),
                "win_rate":       round(prime.wins / prime.total * 100, 1) if prime.total else 0,
                "streak":         prime.streak.streak_length(),
                "streak_letter":  prime.streak.current_letter,
                "pred_logged":    prime_hist,
                "situations_learned": prime_sits,
            },
        }
    return out

# ★ v2.0: Mistake history endpoint
def read_mistake_analysis(game: str, tf: str, target: str) -> dict:
    """
    Kisi stream+target ke liye top galat situations return karo.
    Debugging aur transparency ke liye useful.
    """
    target = str(target).lower().strip()
    if target not in ("color", "size"):
        raise HTTPException(400, "target must be 'color' or 'size'")
    stream_id = resolve_stream(game, tf)
    if not stream_id:
        raise HTTPException(404, "Unknown game/timeframe.")
    st  = STREAMS.get(stream_id)
    if not st:
        raise HTTPException(503, "Engine not ready.")
    srv = st.color if target == "color" else st.size

    # Top situations with most mistakes
    mistake_summary = []
    for sit_key, letter_counts in srv.pred_history.mistake_index.items():
        total_mistakes = sum(letter_counts.values())
        sit_mem        = srv.pred_history.sit_memory.get(sit_key, {})
        for letter, count in letter_counts.items():
            acc  = sit_mem.get(letter, {}).get("acc", 0)
            plays = sit_mem.get(letter, {}).get("plays", 0)
            mistake_summary.append({
                "situation": sit_key,
                "letter":    letter,
                "label":     srv._label(letter),
                "mistakes":  count,
                "total_plays": plays,
                "accuracy":  round(acc * 100, 1),
            })

    mistake_summary.sort(key=lambda x: x["mistakes"], reverse=True)
    return {
        "stream": stream_id,
        "target": target,
        "total_situations": len(srv.pred_history.sit_memory),
        "total_predictions_logged": len(srv.pred_history.pred_log),
        "top_mistakes": mistake_summary[:20],  # top 20 most-wrong situations
    }


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI ROUTER
# ═══════════════════════════════════════════════════════════════════════════
router = APIRouter(prefix="/api/prediction", tags=["prediction"])

@router.get("/{game}/{tf}/{target}")
def _dbg_one(game: str, tf: str, target: str):
    return read_prediction(game, tf, target)

@router.get("/{game}/{tf}")
def _dbg_both(game: str, tf: str):
    return read_both(game, tf)

@router.get("/{game}/{tf}/{target}/mistakes")
def _dbg_mistakes(game: str, tf: str, target: str):
    return read_mistake_analysis(game, tf, target)

@router.get("")
def _dbg_status():
    return engine_status_payload()
