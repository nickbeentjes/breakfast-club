import { MongoClient, Db } from "mongodb";

let client: MongoClient | null = null;

export async function getDb(): Promise<Db> {
  if (!client) {
    const uri = process.env.MONGODB_URI;
    if (!uri) throw new Error("MONGODB_URI environment variable is not set");
    client = new MongoClient(uri);
    await client.connect();
    console.error("MongoDB connected");
  }
  return client.db(process.env.MONGODB_DB_NAME ?? "breakfast-club");
}

export async function closeDb(): Promise<void> {
  if (client) {
    await client.close();
    client = null;
    console.error("MongoDB disconnected");
  }
}
