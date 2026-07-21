"use client";

/** Bulgu yorumları (Sprint 3.2, temel işbirliği): liste + not ekleme. */

import { MessageSquare } from "lucide-react";
import { useState } from "react";

import {
  useAddFindingComment,
  useFindingComments,
} from "@/components/review/use-finding-review";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { FindingKind } from "@/lib/findings";

export type CommentsTarget = { kind: FindingKind; findingId: string; title: string };

const TIME_FORMAT = new Intl.DateTimeFormat("tr-TR", {
  dateStyle: "medium",
  timeStyle: "short",
});

export function FindingCommentsDialog({
  target,
  onClose,
}: {
  target: CommentsTarget | null;
  onClose: () => void;
}) {
  const comments = useFindingComments(target?.kind ?? "requirement", target?.findingId ?? null);
  const addComment = useAddFindingComment();
  const [draft, setDraft] = useState("");

  function submit() {
    const body = draft.trim();
    if (target === null || body === "") return;
    addComment.mutate(
      { kind: target.kind, findingId: target.findingId, body },
      { onSuccess: () => setDraft("") },
    );
  }

  return (
    <Dialog open={target !== null} onOpenChange={(open) => open || onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquare className="size-4 text-ink-3" strokeWidth={1.5} />
            Yorumlar
          </DialogTitle>
          <DialogDescription className="line-clamp-2">{target?.title}</DialogDescription>
        </DialogHeader>

        <ScrollArea className="max-h-72">
          <div className="flex flex-col gap-2 pr-3">
            {comments.isPending && target !== null ? (
              <>
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </>
            ) : comments.isError ? (
              <p className="text-sm text-danger">{comments.error.message}</p>
            ) : (comments.data?.length ?? 0) === 0 ? (
              <p className="rounded-lg border border-dashed p-4 text-sm text-ink-3">
                Henüz yorum yok. İlk notu siz düşün.
              </p>
            ) : (
              comments.data?.map((comment) => (
                <div key={comment.id} className="rounded-lg border bg-surface-2/50 px-3 py-2">
                  <p className="whitespace-pre-wrap text-[13px] leading-5 text-ink-1">
                    {comment.body}
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-ink-3">
                    {TIME_FORMAT.format(new Date(comment.created_at))}
                  </p>
                </div>
              ))
            )}
          </div>
        </ScrollArea>

        <div className="grid gap-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ekip için not düşün…"
            rows={3}
            maxLength={4000}
          />
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={submit}
              disabled={draft.trim() === "" || addComment.isPending}
            >
              {addComment.isPending ? "Ekleniyor…" : "Yorum ekle"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
