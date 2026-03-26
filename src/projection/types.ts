import type { IdentitySection, SensitivityLevel } from "../types.js";

export interface ProjectionDefinition {
  name: string;
  description: string;
  allowed_sections: IdentitySection[];
  allowed_sensitivity: SensitivityLevel[];
  field_allowlist?: Record<string, string[]>;
}

export type ProjectionName = string;
