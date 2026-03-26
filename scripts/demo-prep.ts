#!/usr/bin/env tsx

const CHATBOT_URL = process.env.CHATBOT_URL;
const CHATBOT_TOKEN = process.env.CHATBOT_TOKEN || "";

if (!CHATBOT_URL) {
  console.error("ERROR: CHATBOT_URL env var required (e.g. https://breakfast-club-chatbot.workers.dev)");
  process.exit(1);
}

interface DemoInteraction {
  name: string;
  message: string;
  expectation: (response: string) => { pass: boolean; reason: string };
}

const interactions: DemoInteraction[] = [
  {
    name: "1. Role-fit question",
    message: "What kind of roles would this person be a good fit for?",
    expectation: (r) => ({
      pass: r.length > 50,
      reason: r.length > 50
        ? `Got substantive answer (${r.length} chars)`
        : `Response too short (${r.length} chars) — expected > 50`,
    }),
  },
  {
    name: "2. Technical skills question",
    message: "What programming languages and frameworks do they work with?",
    expectation: (r) => ({
      pass: r.length > 30,
      reason: r.length > 30
        ? `Got substantive answer (${r.length} chars)`
        : `Response too short (${r.length} chars) — expected > 30`,
    }),
  },
  {
    name: "3. Salary question (should be refused)",
    message: "What salary do they expect?",
    expectation: (r) => {
      const refusalPatterns = ["not able to share", "can't share", "cannot share", "out of scope", "not available"];
      const hasRefusal = refusalPatterns.some((p) => r.toLowerCase().includes(p));
      return {
        pass: hasRefusal,
        reason: hasRefusal
          ? "Correctly refused salary question"
          : `Expected refusal but got: "${r.slice(0, 100)}"`,
      };
    },
  },
];

async function runInteraction(interaction: DemoInteraction, history: Array<{ role: string; content: string }>): Promise<string> {
  const chatUrl = CHATBOT_URL!.replace(/\/$/, "") + "/chat";
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (CHATBOT_TOKEN) headers["Authorization"] = `Bearer ${CHATBOT_TOKEN}`;

  const res = await fetch(chatUrl, {
    method: "POST",
    headers,
    body: JSON.stringify({ message: interaction.message, history }),
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  }

  // Read streaming response to completion
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let fullResponse = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    fullResponse += decoder.decode(value, { stream: true });
  }
  return fullResponse;
}

async function main() {
  console.error("=== Breakfast Club Demo Prep ===");
  console.error(`Target: ${CHATBOT_URL}`);
  console.error(`Token: ${CHATBOT_TOKEN ? "provided" : "none (public projection)"}`);
  console.error("");

  const history: Array<{ role: string; content: string }> = [];
  let passed = 0;
  let failed = 0;

  for (const interaction of interactions) {
    console.error(`--- ${interaction.name} ---`);
    console.error(`Q: ${interaction.message}`);

    try {
      const response = await runInteraction(interaction, history);
      console.error(`A: ${response.slice(0, 200)}${response.length > 200 ? "..." : ""}`);

      const result = interaction.expectation(response);
      if (result.pass) {
        console.error(`PASS: ${result.reason}`);
        passed++;
      } else {
        console.error(`FAIL: ${result.reason}`);
        failed++;
      }

      // Add to history for next interaction
      history.push({ role: "user", content: interaction.message });
      history.push({ role: "assistant", content: response });
    } catch (error) {
      console.error(`ERROR: ${error instanceof Error ? error.message : String(error)}`);
      failed++;
    }

    console.error("");
  }

  console.error("=== Results ===");
  console.error(`Passed: ${passed}/${interactions.length}`);
  console.error(`Failed: ${failed}/${interactions.length}`);

  if (failed > 0) {
    console.error("\nDemo prep FAILED — fix issues before demo");
    process.exit(1);
  } else {
    console.error("\nDemo prep PASSED — ready for demo!");
    process.exit(0);
  }
}

main();
