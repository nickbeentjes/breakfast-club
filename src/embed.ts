import OpenAI from "openai";

const EMBEDDING_MODEL = "text-embedding-3-small";
const EMBEDDING_DIMENSIONS = 1536;

let openaiClient: OpenAI | null = null;

function getOpenAI(): OpenAI {
  if (!openaiClient) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) throw new Error("OPENAI_API_KEY environment variable is not set");
    openaiClient = new OpenAI({ apiKey });
  }
  return openaiClient;
}

export async function embedText(text: string): Promise<number[]> {
  if (process.env.STUB_EMBEDDINGS === "1") {
    console.error(`[STUB] Returning zero-vector for: ${text.slice(0, 40)}...`);
    return new Array(EMBEDDING_DIMENSIONS).fill(0);
  }
  const openai = getOpenAI();
  const response = await openai.embeddings.create({
    model: EMBEDDING_MODEL,
    input: text,
  });
  return response.data[0].embedding;
}

export { EMBEDDING_MODEL, EMBEDDING_DIMENSIONS };
