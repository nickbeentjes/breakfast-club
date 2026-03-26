import OpenAI from "openai";
import type { Env } from "../types.js";

export function buildSystemPrompt(identityContext: string, projectionName: string): string {
  return `You are a professional profile assistant. You have access to a person's ${projectionName} profile information.

SCOPE: Answer only questions about role fit, technical skills, project experience, work approach, and logistics like availability and location.

OUT OF SCOPE — respond with "I'm not able to share that information":
- Salary expectations or compensation
- Personal relationships or personal life
- Home address or private contact details
- Political or religious views
- Any information not present in the context below

If the question is ambiguous, interpret it in the most professional context possible.

Identity context:
${identityContext}`;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export async function createChatStream(
  systemPrompt: string,
  history: ChatMessage[],
  message: string,
  env: Env
): Promise<AsyncIterable<OpenAI.Chat.Completions.ChatCompletionChunk>> {
  const openai = new OpenAI({ apiKey: env.OPENAI_API_KEY });

  return openai.chat.completions.create({
    model: "gpt-4o-mini",
    stream: true,
    messages: [
      { role: "system", content: systemPrompt },
      ...history.slice(-10), // limit history to last 10 messages to control token usage
      { role: "user", content: message },
    ],
  });
}
