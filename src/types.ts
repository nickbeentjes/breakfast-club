import type { ObjectId } from "mongodb";

export type SensitivityLevel = "public" | "professional" | "personal" | "private";

export type IdentitySection = "persona" | "skills" | "projects" | "values";

/**
 * MongoDB document shape for identity sections.
 * All identity sections are stored as individual documents in the "identity" collection.
 * The doc_type field is used as a pre-filter in $vectorSearch queries to distinguish
 * identity documents from future memory chunks (Phase 4).
 */
export interface IdentityDocument {
  _id?: ObjectId;
  doc_type: "identity";
  section: IdentitySection;
  sensitivity: SensitivityLevel;
  schema_version: string;
  content: Record<string, unknown>;
  embedding: number[];
  embedding_model: string;
  source_hash?: string;
  git_tree_sha?: string;
  updated_at: Date;
}

/**
 * Full identity document schema — mirrors identity.schema.json
 */
export interface IdentitySchema {
  schema_version: string;
  identity_created: string;
  source: string;
  persona: PersonaSection;
  skills: SkillsSection;
  projects: ProjectsSection;
  values: ValuesSection;
  relationships?: RelationshipsSection;
}

export interface PersonaSection {
  _sensitivity: SensitivityLevel;
  name: string;
  location?: string;
  input_method?: string;
  communication_style: {
    primary: string;
    input_method?: string;
    preferences?: string[];
    dislikes?: string[];
    [key: string]: unknown;
  };
  working_style: {
    approach: string;
    tools?: string;
    methodology?: string;
    autonomy?: string;
    strengths?: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface DomainEntry {
  depth: "beginner" | "intermediate" | "intermediate-advanced" | "advanced" | "expert";
  details: string;
}

export interface SkillsSection {
  _sensitivity: SensitivityLevel;
  primary_stack: Record<string, unknown>;
  domain_expertise: Record<string, DomainEntry>;
  trades_knowledge?: string[];
  [key: string]: unknown;
}

export interface ProjectEntry {
  name: string;
  type: string;
  status: string;
  description: string;
  stack?: string[];
  domain?: string;
  location?: string;
  [key: string]: unknown;
}

export interface ProjectsSection {
  _sensitivity: SensitivityLevel;
  active: ProjectEntry[];
  completed?: Record<string, unknown>[];
  [key: string]: unknown;
}

export interface ValuesSection {
  _sensitivity: SensitivityLevel;
  professional: string[];
  technical_opinions?: string[];
  [key: string]: unknown;
}

export interface RelationshipsSection {
  _sensitivity: SensitivityLevel;
  [key: string]: unknown;
}
