import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

type ChatMessage = {
  id: string;
  text: string;
  createdAt: string;
  threadId: string;
};

const dataFilePath = path.join(process.cwd(), "data", "messages.json");

const readMessages = async (): Promise<ChatMessage[]> => {
  try {
    const file = await fs.readFile(dataFilePath, "utf-8");
    return JSON.parse(file) as ChatMessage[];
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      await fs.mkdir(path.dirname(dataFilePath), { recursive: true });
      await fs.writeFile(dataFilePath, "[]", "utf-8");
      return [];
    }
    throw error;
  }
};

const writeMessages = async (messages: ChatMessage[]) => {
  await fs.mkdir(path.dirname(dataFilePath), { recursive: true });
  await fs.writeFile(dataFilePath, JSON.stringify(messages, null, 2), "utf-8");
};

export async function GET() {
  const messages = await readMessages();
  const normalized = messages.map((message) => ({
    ...message,
    threadId: message.threadId ?? "default",
  }));
  return NextResponse.json({ messages: normalized });
}

export async function POST(request: Request) {
  const body = (await request.json()) as { text?: string; threadId?: string };
  const text = body.text?.trim();
  const threadId = body.threadId?.trim() || "default";
  if (!text) {
    return NextResponse.json(
      { error: "Message text is required." },
      { status: 400 }
    );
  }

  const messages = await readMessages();
  const message: ChatMessage = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    text,
    createdAt: new Date().toISOString(),
    threadId,
  };

  messages.push(message);
  await writeMessages(messages);

  return NextResponse.json({ message });
}

export async function DELETE(request: Request) {
  const { searchParams } = new URL(request.url);
  const threadId = searchParams.get("threadId");
  if (!threadId) {
    await writeMessages([]);
    return NextResponse.json({ messages: [] });
  }
  const messages = await readMessages();
  const filtered = messages.filter(
    (message) => (message.threadId ?? "default") !== threadId
  );
  await writeMessages(filtered);
  return NextResponse.json({ messages: filtered });
}
