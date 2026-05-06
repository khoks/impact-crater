// Wrappers around /api/persons/*.

export interface Person {
  id: string;
  display_name: string;
  notes: string | null;
}

export interface FacePhoto {
  id: string;
  person_id: string;
  content_hash: string;
  face_crop_bbox: [number, number, number, number];
  is_primary: boolean;
}

export async function listPersons(): Promise<Person[]> {
  const r = await fetch("/api/persons");
  if (!r.ok) throw new Error(`GET /api/persons → ${r.status}`);
  return (await r.json()) as Person[];
}

export async function createPerson(displayName: string): Promise<Person> {
  const r = await fetch("/api/persons", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (r.status !== 201) {
    throw new Error(`POST /api/persons → ${r.status}`);
  }
  return (await r.json()) as Person;
}

export async function deletePerson(id: string): Promise<void> {
  const r = await fetch(`/api/persons/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`DELETE /api/persons/${id} → ${r.status}`);
}

export async function listFacePhotos(personId: string): Promise<FacePhoto[]> {
  const r = await fetch(`/api/persons/${personId}/face-photos`);
  if (!r.ok) throw new Error(`GET /api/persons/${personId}/face-photos → ${r.status}`);
  return (await r.json()) as FacePhoto[];
}

export async function addFacePhoto(
  personId: string,
  contentHash: string,
  bbox: [number, number, number, number] = [0, 0, 1, 1],
  isPrimary = false
): Promise<FacePhoto> {
  const r = await fetch(`/api/persons/${personId}/face-photos`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      content_hash: contentHash,
      face_crop_bbox: bbox,
      is_primary: isPrimary,
    }),
  });
  if (r.status !== 201) {
    throw new Error(`POST face-photo → ${r.status}`);
  }
  return (await r.json()) as FacePhoto;
}
