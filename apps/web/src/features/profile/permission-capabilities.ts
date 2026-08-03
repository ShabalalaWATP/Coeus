/**
 * Describe what an account can actually do, in the words the product uses.
 *
 * A permission list is an authorisation implementation detail: "product:
 * create_existing" tells an operator nothing. Each entry below turns one
 * permission into a capability a person would recognise, grouped by the part of
 * Istari it applies to. Permissions with no entry simply do not appear, so a
 * new backend permission can never render as machine text on someone's profile.
 *
 * This is a description of granted access, never a grant: authorisation is
 * enforced server-side at the object and action level.
 */

export type CapabilityArea = {
  capabilities: string[];
  name: string;
};

const AREAS: { name: string; permissions: Record<string, string> }[] = [
  {
    name: "Intelligence Store",
    permissions: {
      "product:search": "Search holdings",
      "store:browse_all": "Browse the full catalogue",
      "product:download": "Download assets",
      "product:read_restricted": "Emergency access with audit",
      "product:create_existing": "Register existing products",
      "product:update_metadata": "Maintain product metadata",
      "product:manage_assets": "Manage product assets",
      "product:publish": "Publish products",
      "product:archive": "Archive products",
      "product:disseminate": "Disseminate products",
    },
  },
  {
    name: "Requests",
    permissions: {
      "ticket:create": "Raise requests",
      "ticket:read_all": "See every request",
      "ticket:add_information": "Add information to requests",
      "ticket:add_comment": "Comment on requests",
      "ticket:transition": "Move requests through the workflow",
      "ticket:consolidate": "Consolidate duplicate requests",
      "chat:use": "Use the intake assistant",
      "rfi:search": "Search before tasking",
      "feedback:create": "Give feedback on delivery",
    },
  },
  {
    name: "Analysis",
    permissions: {
      "analyst:work": "Work assigned analyst tasks",
      "analyst:submit_product": "Submit products for review",
      "product:approve": "Approve analyst products",
    },
  },
  {
    name: "Review and routing",
    permissions: {
      "jioc:review": "Review JIOC routing",
      "jioc:oversight": "Oversee routing on the loop",
      "jioc:intervene": "Intervene in routing",
      "rfa:review": "Review assessment requests",
      "rfa:assign": "Assign analysts",
      "collection:review": "Review collection requests",
      "collection:assign": "Assign collection tasks",
      "qc:review": "Review products in quality control",
      "qc:approve": "Release products",
    },
  },
  {
    name: "Governance",
    permissions: {
      "acg:view": "View need-to-know groups",
      "acg:create": "Create access groups",
      "acg:update": "Update access groups",
      "acg:assign_user": "Assign group membership",
      "acg:assign_product": "Assign product access groups",
      "team:manage": "Manage teams",
      "user:assign_role": "Assign roles",
      "user:create": "Create accounts",
      "user:disable": "Disable accounts",
      "audit:read": "Read the audit trail",
      "system:configure": "Configure the platform",
    },
  },
  {
    name: "Insight",
    permissions: {
      "analytics:view_own": "See your own activity",
      "analytics:view_team": "See team analytics",
      "analytics:view_global": "See platform analytics",
      "feedback:read": "Read delivery feedback",
    },
  },
];

export function capabilityAreas(permissions: readonly string[]): CapabilityArea[] {
  const held = new Set(permissions);
  return AREAS.map((area) => ({
    name: area.name,
    capabilities: Object.entries(area.permissions)
      .filter(([permission]) => held.has(permission))
      .map(([, label]) => label),
  })).filter((area) => area.capabilities.length > 0);
}

/** Permissions that describe signing in rather than what the account can do. */
const ROUTINE_ACCOUNT_PERMISSIONS = new Set([
  "auth:login",
  "auth:logout",
  "user:read_self",
  "user:update_self",
]);

export function describedPermissionCount(permissions: readonly string[]): number {
  return permissions.filter((permission) => !ROUTINE_ACCOUNT_PERMISSIONS.has(permission)).length;
}
