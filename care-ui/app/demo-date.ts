"use client";

const chatStampFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const updatedAtFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const timelineFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "2-digit",
  month: "short",
});

function compact(value: string) {
  return value.replace(/\./g, "").replace(",", "");
}

export function formatChatStamp(iso: string) {
  return compact(chatStampFormatter.format(new Date(iso)));
}

export function formatUpdatedAt(iso: string) {
  return compact(updatedAtFormatter.format(new Date(iso)));
}

export function formatTimelineDate(iso: string) {
  return compact(timelineFormatter.format(new Date(iso)));
}
