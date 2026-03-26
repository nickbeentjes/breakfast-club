import { MongoClient, type Db } from "mongodb";

let client: MongoClient | null = null;

export async function getDb(mongoUri: string): Promise<Db> {
  if (!client) {
    client = new MongoClient(mongoUri, {
      maxPoolSize: 1,
      minPoolSize: 0,
      serverSelectionTimeoutMS: 5000,
    });
  }
  // Re-connect if connection was dropped (M0 idle timeout ~60s)
  try {
    await client.db("admin").command({ ping: 1 });
  } catch {
    client = null;
    client = new MongoClient(mongoUri, {
      maxPoolSize: 1,
      minPoolSize: 0,
      serverSelectionTimeoutMS: 5000,
    });
  }
  await client.connect();
  return client.db("breakfast-club");
}
