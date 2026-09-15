import type { Root } from "mdast";
import type { Direction, Session } from "../../api/types";

type Annotation = Session["annotations"][number];
type AstNode = { type:string; value?:string; children?:AstNode[]; position?:{start?:{offset?:number}}; data?:{hName?:string;hProperties?:Record<string,unknown>} };

function validAnnotations(annotations: Annotation[], pitchLength: number) {
  const sorted = [...annotations]
    .filter((item) => Number.isInteger(item.start) && Number.isInteger(item.end) && item.start >= 0 && item.end > item.start && item.end <= pitchLength)
    .sort((a, b) => a.start - b.start || a.end - b.end);
  return sorted.filter((item, index) => index === 0 || item.start >= sorted[index - 1].end);
}

function markNode(value: string, annotation: Annotation, activeFilter: Direction | "all"): AstNode {
  const visible = activeFilter === "all" || annotation.direction === activeFilter;
  return { type:"evidenceMark", children:[{type:"text",value}], data:{ hName:"mark", hProperties:{ className:[annotation.direction,visible?"":"filtered"].filter(Boolean), dataAnnotationId:annotation.annotation_id, dataEvidenceIds:annotation.evidence_ids.join("|"), dataDirection:annotation.direction, dataVisible:visible?"true":"false" } } };
}

function annotateChildren(parent: AstNode, annotations: Annotation[], activeFilter: Direction | "all") {
  if (!parent.children) return;
  const next: AstNode[] = [];
  for (const node of parent.children) {
    if (node.type !== "text" || typeof node.value !== "string" || node.position?.start?.offset === undefined) {
      annotateChildren(node, annotations, activeFilter);
      next.push(node);
      continue;
    }
    const nodeStart = node.position.start.offset;
    const nodeEnd = nodeStart + node.value.length;
    const overlaps = annotations.filter((item) => item.start < nodeEnd && item.end > nodeStart);
    if (!overlaps.length) { next.push(node); continue; }
    let cursor = 0;
    for (const annotation of overlaps) {
      const start = Math.max(annotation.start, nodeStart) - nodeStart;
      const end = Math.min(annotation.end, nodeEnd) - nodeStart;
      if (start > cursor) next.push({type:"text",value:node.value.slice(cursor,start)});
      if (end > start) next.push(markNode(node.value.slice(start,end),annotation,activeFilter));
      cursor = Math.max(cursor,end);
    }
    if (cursor < node.value.length) next.push({type:"text",value:node.value.slice(cursor)});
  }
  parent.children = next;
}

export function remarkEvidenceAnnotations(annotations: Annotation[], pitchLength: number, activeFilter: Direction | "all") {
  const usable = validAnnotations(annotations,pitchLength);
  return () => (tree: Root) => annotateChildren(tree as AstNode,usable,activeFilter);
}
