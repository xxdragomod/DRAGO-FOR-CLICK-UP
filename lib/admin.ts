// Admin allowlist: comma-separated emails in the ADMIN_EMAILS env variable.
// Example: ADMIN_EMAILS="owner@example.com,second-admin@example.com"
const adminEmails = (process.env.ADMIN_EMAILS || '')
  .split(',')
  .map((e) => e.trim().toLowerCase())
  .filter(Boolean)

export function isAdminEmail(email?: string | null): boolean {
  if (!email) return false
  // Deny by default: if no allowlist is configured, nobody is admin.
  if (adminEmails.length === 0) return false
  return adminEmails.includes(email.trim().toLowerCase())
}
