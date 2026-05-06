// Person library page (M5 baseline).
// MVP scope: list persons + add person + delete person + add face photo
// by content_hash (no in-browser cropper at MVP — that's v1).

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  addFacePhoto,
  createPerson,
  deletePerson,
  listFacePhotos,
  listPersons,
  type FacePhoto,
  type Person,
} from "../api/persons";

export default function PersonLibrary() {
  const [persons, setPersons] = useState<Person[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);

  async function refresh() {
    try {
      setPersons(await listPersons());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onCreate() {
    setError(null);
    if (!newName.trim()) return;
    setAdding(true);
    try {
      await createPerson(newName.trim());
      setNewName("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAdding(false);
    }
  }

  async function onDelete(id: string) {
    setError(null);
    try {
      await deletePerson(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">People</h1>
        <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>

      <p className="mt-2 text-sm text-slate-600">
        The person library lets the curator recognize faces in your photos.
        Add a person, then add up to 5 face photos so the AI can match them.
      </p>

      {error && (
        <p role="alert" className="mt-4 rounded bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <section className="mt-6 rounded border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-700">Add person</h2>
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Display name"
            className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={onCreate}
            disabled={adding || !newName.trim()}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {adding ? "Adding…" : "Add"}
          </button>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-700">
          {persons.length === 0 ? "No people yet." : `${persons.length} ${persons.length === 1 ? "person" : "people"}`}
        </h2>
        <ul className="mt-2 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
          {persons.map((p) => (
            <PersonRow key={p.id} person={p} onDelete={() => onDelete(p.id)} />
          ))}
        </ul>
      </section>
    </main>
  );
}

function PersonRow({ person, onDelete }: { person: Person; onDelete: () => void }) {
  const [faces, setFaces] = useState<FacePhoto[] | null>(null);
  const [hashInput, setHashInput] = useState("");
  const [working, setWorking] = useState(false);

  async function refreshFaces() {
    setFaces(await listFacePhotos(person.id));
  }

  useEffect(() => {
    refreshFaces();
  }, [person.id]);

  async function onAddFace() {
    if (!hashInput.trim()) return;
    setWorking(true);
    try {
      await addFacePhoto(person.id, hashInput.trim());
      setHashInput("");
      await refreshFaces();
    } finally {
      setWorking(false);
    }
  }

  return (
    <li className="px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-slate-900">{person.display_name}</p>
          <p className="text-xs text-slate-500">
            {faces === null
              ? "loading…"
              : `${faces.length} face photo${faces.length === 1 ? "" : "s"}`}
          </p>
        </div>
        <button
          type="button"
          onClick={onDelete}
          className="text-xs text-red-600 hover:text-red-800"
        >
          Delete
        </button>
      </div>
      <div className="mt-2 flex gap-2">
        <input
          type="text"
          value={hashInput}
          onChange={(e) => setHashInput(e.target.value)}
          placeholder="Face photo content_hash (8+ chars)"
          className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs font-mono focus:border-slate-500 focus:outline-none"
        />
        <button
          type="button"
          onClick={onAddFace}
          disabled={working || hashInput.trim().length < 8}
          className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Add face
        </button>
      </div>
    </li>
  );
}
