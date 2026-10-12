"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertCircle,
  Bot,
  Copy,
  Check,
  Loader2,
  RotateCcw,
  Send,
  Square,
  Plus,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { streamQuery } from "@/lib/api/query";
import { apiFetch } from "@/lib/api/client";
import { normalizeSources } from "@/lib/api/normalize";
import { useApp } from "@/lib/context/app-context";
import { suggestedQuestions, type ChatMessage } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ChatInterface() {
  const { activeCollectionId } = useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<{ id: string; title: string }[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function openConversation(id: string, isActive: () => boolean = () => true) {
    setHistoryLoading(true);
    try {
      const history = await apiFetch<{ messages: { id: string; role: string; content: string; sources?: unknown[] | null }[] }>(`/conversations/${id}/messages?limit=100`);
      if (!isActive()) return;
      setConversationId(id);
      setMessages(history.messages.filter((message) => message.role === "user" || message.role === "assistant").map((message) => ({ id: message.id, role: message.role as "user" | "assistant", content: message.content, sources: message.sources ? normalizeSources(message.sources) : undefined })));
    } catch {
      if (isActive()) toast.error("Conversation could not be loaded");
    } finally {
      if (isActive()) setHistoryLoading(false);
    }
  }

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedId(null), 2000);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    let active = true;
    async function loadRecentChat() {
      try {
        const result = await apiFetch<{ chats: { id: string; title: string }[] }>("/conversations?limit=100");
        if (!active) return;
        setConversations(result.chats);
        const recent = result.chats[0];
        if (recent) await openConversation(recent.id, () => active);
      } catch {
        if (active) toast.error("Chat history could not be loaded");
      } finally {
        if (active) setHistoryLoading(false);
      }
    }
    void loadRecentChat();
    return () => { active = false; };
  }, []);

  const sendQuery = useCallback(
    async (query: string, retry = false) => {
      if (!query.trim() || isStreaming) return;

      setLastQuery(query);
      const userMessage: ChatMessage = {
        id: createId(),
        role: "user",
        content: query.trim(),
      };

      const assistantId = createId();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      if (retry) {
        setMessages((prev) => {
          const next = [...prev];
          if (next[next.length - 1]?.role === "assistant") next.pop();
          return [...next, assistantMessage];
        });
      } else {
        setMessages((prev) => [...prev, userMessage, assistantMessage]);
      }

      setInput("");
      setIsStreaming(true);
      abortRef.current = new AbortController();

      try {
        await streamQuery({
          query: query.trim(),
          collectionId: activeCollectionId,
          conversationId,
          onConversationId: (id) => {
            setConversationId(id);
            void apiFetch<{ chats: { id: string; title: string }[] }>("/conversations?limit=100").then((result) => setConversations(result.chats)).catch(() => {});
          },
          signal: abortRef.current.signal,
          onToken: (token) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, content: msg.content + token }
                  : msg
              )
            );
          },
          onSources: (sources) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId ? { ...msg, sources } : msg
              )
            );
          },
          onDone: () => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, isStreaming: false }
                  : msg
              )
            );
          },
          onError: (error) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? {
                      ...msg,
                      isStreaming: false,
                      error: error.message,
                      content: msg.content || "Something went wrong.",
                    }
                  : msg
              )
            );
          },
        });
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const message =
          err instanceof Error ? err.message : "Failed to get response";
        toast.error(message);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantId
              ? { ...msg, isStreaming: false, error: message }
              : msg
          )
        );
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [activeCollectionId, conversationId, isStreaming]
  );

  const stopGeneration = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((msg) =>
        msg.isStreaming ? { ...msg, isStreaming: false } : msg
      )
    );
  };

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col gap-4">
      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between gap-4 border-b border-border/60 pb-4">
          <div>
            <CardTitle>Chat</CardTitle>
            <CardDescription>Ask questions about your uploaded documents</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            {conversations.length > 0 && <select aria-label="Recent conversations" value={conversationId ?? ""} onChange={(event) => { const id = event.target.value; if (id) void openConversation(id); else { setConversationId(null); setMessages([]); } }} className="h-9 max-w-44 rounded-lg border border-input bg-background px-2 text-xs">
              {conversations.map((conversation) => <option key={conversation.id} value={conversation.id}>{conversation.title}</option>)}
            </select>}
            <Button type="button" variant="outline" size="sm" onClick={() => { setConversationId(null); setMessages([]); }}><Plus className="size-4" /><span className="hidden sm:inline">New chat</span></Button>
          </div>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col p-0">
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6">
            {historyLoading ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Loading chat historyâ€¦</div>
            ) : messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
                <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Bot className="size-7" />
                </div>
                <div>
                  <p className="font-medium">Start a conversation</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Ask anything about your knowledge base
                  </p>
                </div>
                <div className="flex flex-wrap justify-center gap-2">
                  {suggestedQuestions.map((question) => (
                    <Button
                      key={question}
                      variant="outline"
                      size="sm"
                      className="h-auto whitespace-normal px-3 py-2 text-left"
                      disabled={isStreaming}
                      onClick={() => sendQuery(question)}
                    >
                      {question}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={cn(
                      "flex gap-3",
                      message.role === "user" ? "justify-end" : "justify-start"
                    )}
                  >
                    {message.role === "assistant" && (
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <Bot className="size-4" />
                      </div>
                    )}
                    <div
                      className={cn(
                        "max-w-[85%] rounded-xl px-4 py-3 text-sm",
                        message.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted"
                      )}
                    >
                      {message.role === "assistant" ? (
                        <div className="prose prose-sm dark:prose-invert max-w-none relative group">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.content ||
                              (message.isStreaming ? "Ã¢â€“Â" : "")}
                          </ReactMarkdown>
                          {message.isStreaming && (
                            <span className="ml-0.5 inline-block animate-pulse">
                              Ã¢â€“Â
                            </span>
                          )}
                          {!message.isStreaming && message.content && (
                            <div className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="size-6 text-muted-foreground hover:text-foreground"
                                onClick={() => copyToClipboard(message.content, message.id)}
                              >
                                {copiedId === message.id ? (
                                  <Check className="size-3 text-emerald-500" />
                                ) : (
                                  <Copy className="size-3" />
                                )}
                              </Button>
                            </div>
                          )}
                        </div>
                      ) : (
                        message.content
                      )}

                      {message.error && (
                        <div className="mt-2 flex items-center gap-2 text-xs text-destructive">
                          <AlertCircle className="size-3.5" />
                          {message.error}
                        </div>
                      )}

                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-3 space-y-2 border-t border-border/60 pt-3">
                          <p className="text-xs font-medium text-muted-foreground">
                            Sources
                          </p>
                          {message.sources.map((source, i) => (
                            <div
                              key={i}
                              className="rounded-lg bg-background/60 px-3 py-2 text-xs"
                            >
                              {source.documentName && (
                                <p className="font-medium">
                                  {source.documentName}
                                  {source.page ? ` Ã‚Â· p.${source.page}` : ""}
                                </p>
                              )}
                              {source.chunkText && (
                                <p className="mt-1 text-muted-foreground line-clamp-3">
                                  {source.chunkText}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {message.error && lastQuery && !message.isStreaming && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-2 h-7 px-2 text-xs"
                          onClick={() => sendQuery(lastQuery, true)}
                        >
                          <RotateCcw className="size-3" />
                          Retry
                        </Button>
                      )}
                    </div>
                    {message.role === "user" && (
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                        <User className="size-4 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>
            )}
          </div>

          <div className="border-t border-border/60 p-4">
            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                sendQuery(input);
              }}
            >
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about your documentsÃ¢â‚¬Â¦"
                className="min-h-[44px] resize-none"
                rows={1}
                disabled={isStreaming}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendQuery(input);
                  }
                }}
              />
              {isStreaming ? (
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={stopGeneration}
                >
                  <Square className="size-4" />
                </Button>
              ) : (
                <Button type="submit" size="icon" disabled={!input.trim()}>
                  {isStreaming ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Send className="size-4" />
                  )}
                </Button>
              )}
            </form>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

