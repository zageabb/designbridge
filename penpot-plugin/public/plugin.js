penpot.ui.open("DesignBridge Importer", "index.html", { width: 460, height: 720 });

const componentMap = new Map();
const colorMap = new Map();

function tokenValue(value) {
  return value && typeof value === "object" && "value" in value ? value.value : value;
}

function resolveFill(node, document) {
  if (node.fill_token) {
    const token = document.tokens?.colors?.[node.fill_token];
    if (token) return tokenValue(token);
  }
  return node.fill;
}

function createColorLibrary(document) {
  const colors = document.tokens?.colors || {};
  for (const [name, raw] of Object.entries(colors)) {
    try {
      const color = penpot.library.local.createColor();
      color.name = name;
      color.color = tokenValue(raw);
      color.setPluginData("designbridge:token", name);
      colorMap.set(name, color);
    } catch (error) {
      console.warn("DesignBridge color token import failed", name, error);
    }
  }
}

function applyFill(shape, node, document) {
  const fill = resolveFill(node, document);
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

function tagShape(shape, node) {
  shape.setPluginData("designbridge:id", node.id);
  shape.setPluginData("designbridge:type", node.type);
  if (node.fill_token) shape.setPluginData("designbridge:fill-token", node.fill_token);
}

function createPrimitive(node, parent, document) {
  let shape;
  if (node.type === "frame" || node.type === "component") {
    shape = penpot.createBoard();
    shape.name = node.name;
    applySize(shape, node);
    applyFill(shape, node, document);
    applyLayout(shape, node.layout);
  } else if (node.type === "text") {
    shape = penpot.createText(node.text || " ");
    if (!shape) return null;
    shape.name = node.name;
    applySize(shape, node);
  } else {
    shape = penpot.createRectangle();
    shape.name = node.name;
    applySize(shape, node);
    applyFill(shape, node, document);
  }

  tagShape(shape, node);
  parent.appendChild(shape);

  if (shape.type === "board") {
    for (const child of node.children || []) createNode(child, shape, document);
  }
  return shape;
}

function createNode(node, parent, document) {
  if (node.type === "instance") {
    const component = componentMap.get(node.component_id);
    if (!component) throw new Error("Unknown component: " + node.component_id);
    const instance = component.instance();
    instance.name = node.name;
    applySize(instance, node);
    tagShape(instance, node);
    parent.appendChild(instance);
    return instance;
  }
  return createPrimitive(node, parent, document);
}

async function createComponents(document) {
  if (!(document.components || []).length) return;
  const page = penpot.createPage();
  page.name = "Design System";
  await penpot.openPage(page);

  let y = 0;
  for (const componentNode of document.components) {
    const mainShape = createPrimitive({ ...componentNode, x: 0, y }, page.root, document);
    const libraryComponent = penpot.library.local.createComponent([mainShape]);
    componentMap.set(componentNode.id, libraryComponent);
    try {
      libraryComponent.setPluginData("designbridge:id", componentNode.id);
    } catch (_) {}
    y += (componentNode.height || 120) + 80;
  }
}

async function importDocument(document) {
  if (!document || document.format !== "designbridge" || document.version !== "0.1") {
    throw new Error("Unsupported DesignBridge document");
  }
  componentMap.clear();
  colorMap.clear();
  createColorLibrary(document);
  await createComponents(document);

  const pages = document.pages || [];
  for (const pageModel of pages) {
    const page = penpot.createPage();
    page.name = pageModel.name;
    await penpot.openPage(page);
    for (const node of pageModel.children || []) createNode(node, page.root, document);
  }
  penpot.currentFile?.setPluginData("designbridge:document-id", document.document.id);
  return {
    pages: pages.length,
    components: componentMap.size,
    colors: colorMap.size,
    name: document.document.name
  };
}

function indexDocumentNodes(document) {
  const nodes = new Map();
  function walk(node) {
    nodes.set(node.id, node);
    for (const child of node.children || []) walk(child);
  }
  for (const component of document.components || []) walk(component);
  for (const page of document.pages || []) {
    for (const node of page.children || []) walk(node);
  }
  return nodes;
}

function linkedShapesOnCurrentPage() {
  return (penpot.currentPage?.findShapes() || []).filter(
    shape => Boolean(shape.getPluginData("designbridge:id"))
  );
}

function updateLinkedShapes(document) {
  const nodes = indexDocumentNodes(document);
  let updated = 0;
  let missing = 0;

  for (const shape of linkedShapesOnCurrentPage()) {
    const id = shape.getPluginData("designbridge:id");
    const node = nodes.get(id);
    if (!node) {
      missing += 1;
      continue;
    }

    shape.name = node.name;
    if (typeof node.x === "number") shape.x = node.x;
    if (typeof node.y === "number") shape.y = node.y;
    if (
      typeof node.width === "number" &&
      typeof node.height === "number" &&
      typeof shape.resize === "function"
    ) {
      shape.resize(node.width, node.height);
    }

    const fill = resolveFill(node, document);
    if (fill && shape.type !== "text") {
      shape.fills = [{ fillColor: fill, fillOpacity: 1 }];
    }
    if (shape.type === "text" && typeof node.text === "string") {
      shape.characters = node.text;
    }
    tagShape(shape, node);
    updated += 1;
  }

  return { updated, missing };
}

penpot.ui.onMessage(async (message) => {
  if (message?.type === "designbridge:get-selection") {
    sendSelection();
    return;
  }
  if (message?.type === "designbridge:get-context") {
    sendContext();
    return;
  }
  if (message?.type === "designbridge:update-linked") {
    try {
      const result = updateLinkedShapes(message.document);
      penpot.ui.sendMessage({ type: "designbridge:update-linked-result", ok: true, result });
      sendSelection();
    } catch (error) {
      penpot.ui.sendMessage({
        type: "designbridge:update-linked-result",
        ok: false,
        error: error instanceof Error ? error.message : String(error)
      });
    }
    return;
  }
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


function shapeFill(shape) {
  const fills = shape.fills;
  if (Array.isArray(fills) && fills.length && fills[0]?.fillColor) {
    return fills[0].fillColor;
  }
  return null;
}

function serializeSelection() {
  return (penpot.selection || []).map(shape => ({
    penpot_id: shape.id,
    designbridge_id: shape.getPluginData("designbridge:id") || null,
    designbridge_type: shape.getPluginData("designbridge:type") || null,
    name: shape.name,
    type: shape.type,
    x: shape.x,
    y: shape.y,
    width: shape.width,
    height: shape.height,
    text: shape.type === "text" ? shape.characters : null,
    fill: shapeFill(shape)
  }));
}

function sendSelection() {
  penpot.ui.sendMessage({
    type: "designbridge:selection",
    selection: serializeSelection()
  });
}

function sendContext() {
  penpot.ui.sendMessage({
    type: "designbridge:context",
    project_id: penpot.currentFile?.getPluginData("designbridge:document-id") || null,
    file_name: penpot.currentFile?.name || null,
    page_name: penpot.currentPage?.name || null
  });
}

penpot.on("selectionchange", () => sendSelection());
sendContext();
sendSelection();
