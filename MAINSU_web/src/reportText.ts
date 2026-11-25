// Internal retrieval identifiers are kept in the saved analysis, not in student-facing text.
export function reportText(text:string):string {
  return text.replace(/[（(]\s*doc\d+\s*:\s*event[_-]\w+(?:\s*[、,，;；]\s*doc\d+\s*:\s*event[_-]\w+)*\s*[)）]/gi,'').trim();
}
