penpot.ui.open("DesignBridge Importer", "index.html", { width: 420, height: 620 });

function applyFill(shape, fill) {
  if (fill) shape.fills = [{ fillColor: fill, fillOpacity: 1 }];
}

function applySize(shape, node) {
  if (node.width && node.height && typeof shape.resize === "function") {
    shape.resize(node.width, node.height);
  }
  if (typeof node.x === "number") shape.x = node.x;
  if (typeof node.y === "number") shape.y = node.y;
}

function applyLayout(board, layout) {
  if (!layout) return;
  const flex = board.addFlexLayout();
  flex.dir = layout.direction === "horizontal" ? "row" : "column";
  flex.rowGap = layout.gap || 0;
  flex.columnGap = layout.gap || 0;
  flex.verticalPadding = layout.padding || 0;
  flex.horizontalPadding = layout.padding || 0;
  flex.alignItems = layout.align || "start";
}

function createNode(node, parent) {
  let shape;
  if (node.type === "frame" || node.type === "component") {
    shape = penpot.createBoard();
    shape.name = node.name;
    applySize(shape, node);
    applyFill(shape, node.fill);
    applyLayout(shape, node.layout);
  } else if (node.type === "text") {
    shape = penpot.createText(node.text || " ");
    if (!shape) return null;
    shape.name = node.name;
    if (typeof node.x === "number") shape.x = node.x;
    if (typeof node.y === "number") shape.y = node.y;
  } else {
    shape = penpot.createRectangle();
    shape.name = node.name;
    applySize(shape, node);
    applyFill(shape, node.fill || "#FFFFFF");
  }

  shape.setPluginData("designbridge:id", node.id);
  shape.setPluginData("designbridge:type", node.type);
  parent.appendChild(shape);

  if (shape.type === "board") {
    for (const child of node.children || []) createNode(child, shape);
  }
  return shape;
}

async function importDocument(document) {
  if (!document || document.format !== "designbridge" || document.version !== "0.1") {
    throw new Error("Unsupported DesignBridge document");
  }
  const pages = document.pages || [];
  for (const pageModel of pages) {
    const page = penpot.createPage();
    page.name = pageModel.name;
    await penpot.openPage(page);
    for (const node of pageModel.children || []) createNode(node, page.root);
  }
  penpot.currentFile?.setPluginData("designbridge:document-id", document.document.id);
  return { pages: pages.length, name: document.document.name };
}

penpot.ui.onMessage(async (message) => {
  if (message?.type !== "designbridge:import") return;
  try {
    const result = await importDocument(message.document);
    penpot.ui.sendMessage({ type: "designbridge:import-result", ok: true, result });
  } catch (error) {
    penpot.ui.sendMessage({
      type: "designbridge:import-result",
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
});
