"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Icon } from "./icon";

type Note = { id: string; title: string; body: string; createdAt: string; updatedAt: string };
const storageKey = "seenx.learning-notes.v1";

function readNotes(raw: string | null): Note[] {
  if (raw === null) return [];
  const value: unknown = JSON.parse(raw);
  if (!Array.isArray(value) || !value.every((note: unknown) => {
    if (!note || typeof note !== "object") return false;
    const item = note as Record<string, unknown>;
    return ["id", "title", "body", "createdAt", "updatedAt"].every((key) => typeof item[key] === "string")
      && Number.isFinite(Date.parse(item.createdAt as string))
      && Number.isFinite(Date.parse(item.updatedAt as string));
  })) throw new Error("Stored notes are not in the expected format.");
  return value as Note[];
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function LearningNotebook() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [ready, setReady] = useState(false);
  const [canSave, setCanSave] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const titleInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function load() {
      try {
        setNotes(readNotes(window.localStorage.getItem(storageKey)));
        setCanSave(true);
      } catch {
        setCanSave(false);
        setMessage("Browser notes could not be read. Existing storage has been left untouched. You can still write and copy your draft.");
      }
      setReady(true);
    }
    load();
    function onStorage(event: StorageEvent) {
      if (event.storageArea === window.localStorage && (event.key === storageKey || event.key === null)) load();
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  function persist(next: Note[], success: string) {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(next));
      setNotes(next);
      setMessage(success);
      return true;
    } catch {
      setMessage("Could not save in this browser. Your draft is still here; copy it somewhere safe and try again.");
      return false;
    }
  }

  function resetDraft() {
    setTitle("");
    setBody("");
    setEditing(null);
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!body.trim() || !canSave) return;
    const now = new Date().toISOString();
    const existing = notes.find((note) => note.id === editing);
    if (editing && !existing) {
      setMessage("This note changed in another tab. Copy your draft, then cancel editing and save it as a new note.");
      return;
    }
    const note: Note = {
      id: existing?.id ?? crypto.randomUUID(),
      title: title.trim() || "A thought along the way",
      body: body.trim(),
      createdAt: existing?.createdAt ?? now,
      updatedAt: now,
    };
    const next = existing ? notes.map((item) => item.id === note.id ? note : item) : [note, ...notes];
    if (persist(next, existing ? "Changes saved in this browser." : "Note saved in this browser.")) resetDraft();
  }

  function edit(note: Note) {
    setEditing(note.id);
    setTitle(note.title);
    setBody(note.body);
    setMessage("");
    titleInput.current?.focus();
  }

  function remove(id: string) {
    if (persist(notes.filter((note) => note.id !== id), "Note deleted from this browser.")) {
      if (editing === id) resetDraft();
      setDeleting(null);
    }
  }

  function exportNotes() {
    const text = ["# My seenX learning notes", "", ...notes.flatMap((note) => [
      `## ${note.title}`, `Created: ${note.createdAt}`, `Updated: ${note.updatedAt}`, "", note.body, "",
    ])].join("\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "seenx-learning-notes.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage("Exported saved notes as a Markdown file.");
  }

  return (
    <div className="personal-notebook">
      <div className="notebook-storage"><Icon name="lock" size={16} /><p>Saved only in this browser on this site address. Export a copy to keep your notes if you change browsers, change the site address, or clear browser data.</p></div>
      <form onSubmit={save} className="notebook-form">
        <label htmlFor="note-title">{editing ? "Edit note title" : "Give it a title"}<span>Optional</span></label>
        <input ref={titleInput} id="note-title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} placeholder="Something clicked today…" />
        <label htmlFor="note-body">My thoughts</label>
        <textarea id="note-body" value={body} onChange={(event) => setBody(event.target.value)} required maxLength={20000} rows={6} placeholder="What I understood, what I’m wondering, or why I made a decision…" aria-describedby="note-draft-help" />
        <p id="note-draft-help" className="notebook-draft-help">Use Save note to keep this draft. Unsaved text is lost if you leave or reload the page.</p>
        <div className="notebook-actions"><button className="button button-dark button-small" type="submit" disabled={!ready || !canSave || !body.trim()}>{editing ? "Save changes" : "Save note"}<Icon name="check" size={15} /></button>{editing && <button type="button" className="notebook-text-button" onClick={resetDraft}>Cancel edit</button>}<button type="button" className="notebook-text-button notebook-export" disabled={!ready || notes.length === 0} onClick={exportNotes}>Export saved notes <Icon name="diagonal" size={13} /></button></div>
      </form>
      <p className="notebook-message" role="status">{message}</p>
      {!ready ? <p className="notebook-empty">Loading your notes…</p> : notes.length === 0 ? <div className="notebook-empty"><Icon name="code" size={22} /><strong>A blank page is a good start.</strong><p>Your first thought, question, or small discovery goes here.</p></div> : (
        <div className="personal-notes">{notes.map((note) => <article key={note.id} className="personal-note"><div className="personal-note-top"><time dateTime={note.updatedAt}>{displayDate(note.updatedAt)}</time><div><button type="button" onClick={() => edit(note)} disabled={editing !== null || !!body.trim()} aria-label={`Edit ${note.title}`}>Edit</button><button type="button" onClick={() => setDeleting(note.id)} aria-label={`Delete ${note.title}`}>Delete</button></div></div><h3>{note.title}</h3><p>{note.body}</p>{deleting === note.id && <div className="note-delete-confirm"><span>Delete this note?</span><button type="button" onClick={() => remove(note.id)}>Delete note</button><button type="button" onClick={() => setDeleting(null)}>Keep it</button></div>}</article>)}</div>
      )}
    </div>
  );
}
