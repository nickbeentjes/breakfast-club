export interface Env {
  MONGODB_URI: string;
  OPENAI_API_KEY: string;
  GITHUB_TOKEN: string;
  GITHUB_OWNER: string;
  GITHUB_PRIVATE_REPO: string;
  TOKEN_MAP: string; // JSON string: {"tok_xxx": "professional", "tok_yyy": "public"}
}
