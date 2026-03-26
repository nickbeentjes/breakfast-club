import { MongoClient } from "mongodb";

async function main(): Promise<void> {
  const uri = process.env.MONGODB_URI;
  if (!uri) throw new Error("MONGODB_URI not set");
  const dbName = process.env.MONGODB_DB_NAME ?? "breakfast-club";

  const client = new MongoClient(uri);
  await client.connect();
  console.error("Connected to MongoDB Atlas");

  const db = client.db(dbName);
  const collection = db.collection("identity");

  try {
    const result = await collection.createSearchIndex({
      name: "identity_vector_index",
      type: "vectorSearch",
      definition: {
        fields: [
          { type: "vector", path: "embedding", numDimensions: 1536, similarity: "cosine" },
          { type: "filter", path: "doc_type" },
          { type: "filter", path: "sensitivity" },
        ],
      },
    });
    console.error("Vector search index created:", result);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("already exists")) {
      console.error("Index already exists — skipping creation");
    } else {
      throw e;
    }
  } finally {
    await client.close();
    console.error("Done");
  }
}

main().catch((err: unknown) => {
  console.error("Failed:", err);
  process.exit(1);
});
