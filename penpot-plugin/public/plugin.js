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

function setFlexLayout(flex, layout) {
  if (!flex || !layout) return;
  flex.dir = layout.direction === "horizontal" ? "row" : "column";
  flex.rowGap = layout.gap || 0;
  flex.columnGap = layout.gap || 0;
  flex.verticalPadding = layout.padding || 0;
  flex.horizontalPadding = layout.padding || 0;
  flex.alignItems = layout.align || "start";
}

function applyLayout(board, layout) {
  if (!layout) return;
  const flex = board.addFlexLayout();
  setFlexLayout(flex, layout);
}

function tagShape(shape, node) {
  shape.setPluginData("designbridge:id", node.id);
  shape.setPluginData("designbridge:type", node.type);
  if (node.fill_token) shape.setPluginData("designbridge:fill-token", node.fill_token);
  if (node.component_id) shape.setPluginData("designbridge:component-id", node.component_id);
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


function applyInstanceOverrides(instance, node) {
  const overrides = node.overrides || {};
  if (!Object.keys(overrides).length) return 0;
  let updated = 0;

  function walk(shape) {
    for (const child of shape.children || []) {
      const linkedId = child.getPluginData("designbridge:id");
      const values = overrides[linkedId];
      if (values) {
        if (typeof values.name === "string") child.name = values.name;
        if (child.type === "text" && typeof values.text === "string") {
          child.characters = values.text;
        }
        if (child.type !== "text" && typeof values.fill === "string") {
          child.fills = [{ fillColor: values.fill, fillOpacity: 1 }];
        }
        updated += 1;
      }
      walk(child);
    }
  }

  walk(instance);
  return updated;
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
    applyInstanceOverrides(instance, node);
    return instance;
  }
  return createPrimitive(node, parent, document);
}

async function createComponents(document) {
  if (!(document.components || []).length) return;
  const page = penpot.createPage();
  page.name = "Design System";
  page.setPluginData("designbridge:page-id", "__components__");
  await penpot.openPage(page);

  let y = 0;
  for (const componentNode of document.components) {
    const mainShape = createPrimitive({ ...componentNode, x: 0, y }, page.root, document);
    const libraryComponent = penpot.library.local.createComponent([mainShape]);
    componentMap.set(componentNode.id, libraryComponent);
    try {
      libraryComponent.setPluginData("designbridge:id", componentNode.id);
      if (componentNode.variant_group) {
        libraryComponent.setPluginData("designbridge:variant-group", componentNode.variant_group);
        libraryComponent.setPluginData(
          "designbridge:variant-properties",
          JSON.stringify(componentNode.variant_properties || {})
        );
      }
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
    page.setPluginData("designbridge:page-id", pageModel.id);
    await penpot.openPage(page);
    for (const node of pageModel.children || []) createNode(node, page.root, document);
  }
  penpot.currentFile?.setPluginData("designbridge:document-id", document.document.id);
  penpot.currentFile?.setPluginData("designbridge:revision", "0");
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

function linkedShapesAcrossDocument() {
  const pages = penpot.currentFile?.pages || [];
  const rows = [];
  for (const page of pages) {
    for (const shape of page.findShapes()) {
      if (!shape.getPluginData("designbridge:id")) continue;
      rows.push({ page, shape });
    }
  }
  return rows;
}




function findLibraryComponent(componentId) {
  const libraries = [
    penpot.library.local,
    ...(penpot.library.connected || [])
  ];
  for (const library of libraries) {
    const match = (library.components || []).find(
      component => component.getPluginData("designbridge:id") === componentId
    );
    if (match) return match;
  }
  return null;
}

function switchInstanceVariant(instanceId, targetComponentId, remappedOverrides) {
  const row = linkedShapesAcrossDocument().find(
    item => item.shape.getPluginData("designbridge:id") === instanceId
  );
  if (!row) throw new Error("DesignBridge instance is not present in Penpot: " + instanceId);

  const shape = row.shape;
  if (!(typeof shape.isComponentCopyInstance === "function" && shape.isComponentCopyInstance())) {
    throw new Error("Target shape is not a Penpot component copy instance.");
  }

  const target = findLibraryComponent(targetComponentId);
  if (!target) {
    throw new Error("Target DesignBridge component is not available in Penpot: " + targetComponentId);
  }

  shape.swapComponent(target);
  shape.setPluginData("designbridge:id", instanceId);
  shape.setPluginData("designbridge:type", "instance");
  shape.setPluginData("designbridge:component-id", targetComponentId);
  applyInstanceOverrides(shape, { overrides: remappedOverrides || {} });

  return {
    instance_id: instanceId,
    target_component_id: targetComponentId
  };
}

function componentNodeIndex(document) {
  const result = new Map();
  function walk(node, componentId) {
    result.set(node.id, { node, componentId });
    for (const child of node.children || []) walk(child, componentId);
  }
  for (const component of document.components || []) {
    walk(component, component.id);
  }
  return result;
}

function updateComponentDefinitions(document, componentIds) {
  const wanted = new Set(componentIds || []);
  const index = componentNodeIndex(document);
  let updated = 0;

  for (const item of linkedShapesAcrossDocument()) {
    const shape = item.shape;
    const meta = componentMetadata(shape);
    if (!["main_root", "main_member"].includes(meta.component_role)) continue;

    const linkedId = shape.getPluginData("designbridge:id");
    const entry = index.get(linkedId);
    if (!entry || (wanted.size && !wanted.has(entry.componentId))) continue;

    const node = entry.node;
    shape.name = node.name;
    if (shape.type === "text" && typeof node.text === "string") {
      shape.characters = node.text;
    }
    const fill = resolveFill(node, document);
    if (fill && shape.type !== "text") {
      shape.fills = [{ fillColor: fill, fillOpacity: 1 }];
    }
    updated += 1;
  }

  return { updated };
}

function applyPropertyUpdates(updates) {
  const byId = new Map(linkedShapesAcrossDocument().map(item => [item.shape.getPluginData("designbridge:id"), item.shape]));
  let updated = 0;
  for (const item of updates || []) {
    const shape = byId.get(item.node_id);
    if (!shape) continue;
    const value = item.value;
    if (item.property === "name") shape.name = value;
    else if (item.property === "x" && typeof value === "number") shape.x = value;
    else if (item.property === "y" && typeof value === "number") shape.y = value;
    else if (item.property === "width" && typeof value === "number" && typeof shape.resize === "function") shape.resize(value, shape.height);
    else if (item.property === "height" && typeof value === "number" && typeof shape.resize === "function") shape.resize(shape.width, value);
    else if (item.property === "text" && shape.type === "text" && typeof value === "string") shape.characters = value;
    else if (item.property === "fill" && value && shape.type !== "text") shape.fills = [{ fillColor: value, fillOpacity: 1 }];
    else if (item.property === "layout" && shape.type === "board" && value) {
      const flex = shape.flex || shape.layout || null;
      if (flex) setFlexLayout(flex, value);
    } else continue;
    updated += 1;
  }
  return { updated };
}

function updateLinkedShapes(document, nodeIds=null) {
  const nodes = indexDocumentNodes(document);
  const allowed = nodeIds ? new Set(nodeIds) : null;
  let updated = 0;
  let missing = 0;

  for (const shape of linkedShapesOnCurrentPage()) {
    const linkedId = shape.getPluginData("designbridge:id");
    if (allowed && !allowed.has(linkedId)) continue;
    const id = linkedId;
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
    if (shape.type === "board" && node.layout) {
      const flex = shape.flex || shape.layout || null;
      if (flex) setFlexLayout(flex, node.layout);
    }
    tagShape(shape, node);
    if (node.type === "instance") applyInstanceOverrides(shape, node);
    updated += 1;
  }

  return { updated, missing };
}

penpot.ui.onMessage(async (message) => {
  if (message?.type === "designbridge:get-selection") {
    sendSelection();
    return;
  }
  if (message?.type === "designbridge:get-linked-snapshot") {
    penpot.ui.sendMessage({
      type: "designbridge:linked-snapshot",
      snapshots: linkedShapesOnCurrentPage().map(serializeShape)
    });
    return;
  }
  if (message?.type === "designbridge:get-document-snapshot") {
    penpot.ui.sendMessage({
      type: "designbridge:document-snapshot",
      snapshots: linkedShapesAcrossDocument().map(item => ({
        ...serializeShape(item.shape),
        page_id: item.page.id,
        page_name: item.page.name,
        designbridge_page_id: item.page.getPluginData("designbridge:page-id") || null
      })),
      pages: (penpot.currentFile?.pages || []).map(page => ({
        page_id: page.id,
        page_name: page.name,
        designbridge_page_id: page.getPluginData("designbridge:page-id") || null
      }))
    });
    return;
  }
  if (message?.type === "designbridge:get-context") {
    sendContext();
    return;
  }
  if (message?.type === "designbridge:set-revision") {
    if (penpot.currentFile && Number.isFinite(Number(message.revision))) {
      penpot.currentFile.setPluginData("designbridge:revision", String(Number(message.revision)));
      sendContext();
    }
    return;
  }
  if (message?.type === "designbridge:switch-instance-variant") {
    try {
      const result = switchInstanceVariant(
        message.instance_id,
        message.target_component_id,
        message.remapped_overrides || {}
      );
      penpot.ui.sendMessage({
        type: "designbridge:variant-switch-result",
        request_id: message.request_id || null,
        ok: true,
        result
      });
      sendSelection();
    } catch (error) {
      penpot.ui.sendMessage({
        type: "designbridge:variant-switch-result",
        request_id: message.request_id || null,
        ok: false,
        error: error instanceof Error ? error.message : String(error)
      });
    }
    return;
  }
  if (message?.type === "designbridge:update-component-definitions") {
    try {
      const result = updateComponentDefinitions(
        message.document,
        message.component_ids || []
      );
      penpot.ui.sendMessage({
        type: "designbridge:component-definition-update-result",
        ok: true,
        result
      });
      sendSelection();
    } catch (error) {
      penpot.ui.sendMessage({
        type: "designbridge:component-definition-update-result",
        ok: false,
        error: error instanceof Error ? error.message : String(error)
      });
    }
    return;
  }
  if (message?.type === "designbridge:apply-property-updates") {
    try {
      const result = applyPropertyUpdates(message.updates || []);
      penpot.ui.sendMessage({ type: "designbridge:property-update-result", ok: true, result });
      sendSelection();
    } catch (error) {
      penpot.ui.sendMessage({ type: "designbridge:property-update-result", ok: false, error: error instanceof Error ? error.message : String(error) });
    }
    return;
  }
  if (message?.type === "designbridge:update-linked") {
    try {
      const result = updateLinkedShapes(message.document, message.node_ids || null);
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

function flexSnapshot(shape) {
  if (shape.type !== "board") return {};
  const flex = shape.flex || shape.layout || null;
  if (!flex) return {};
  const direction = flex.dir === "row" ? "horizontal" : flex.dir === "column" ? "vertical" : null;
  const gap = typeof flex.rowGap === "number" && typeof flex.columnGap === "number"
    ? Math.max(flex.rowGap, flex.columnGap)
    : null;
  const paddingValues = [flex.verticalPadding, flex.horizontalPadding].filter(v => typeof v === "number");
  const padding = paddingValues.length ? Math.max(...paddingValues) : null;
  const align = ["start","center","end","stretch"].includes(flex.alignItems) ? flex.alignItems : null;
  return {
    layout_direction: direction,
    layout_gap: gap,
    layout_padding: padding,
    layout_align: align
  };
}


function componentMetadata(shape) {
  try {
    const isRoot = typeof shape.isComponentRoot === "function" && shape.isComponentRoot();
    const isMain = typeof shape.isComponentMainInstance === "function" && shape.isComponentMainInstance();
    const isCopy = typeof shape.isComponentCopyInstance === "function" && shape.isComponentCopyInstance();
    const component = typeof shape.component === "function" ? shape.component() : null;
    const root = typeof shape.componentRoot === "function" ? shape.componentRoot() : null;
    let role = "basic";
    if (isRoot && isMain) role = "main_root";
    else if (isRoot && isCopy) role = "copy_root";
    else if (isMain) role = "main_member";
    else if (isCopy) role = "copy_member";
    return {
      component_role: role,
      component_id: component?.getPluginData("designbridge:id") || shape.getPluginData("designbridge:component-id") || null,
      component_root_designbridge_id: root?.getPluginData("designbridge:id") || null
    };
  } catch (_) {
    return {
      component_role: "basic",
      component_id: shape.getPluginData("designbridge:component-id") || null,
      component_root_designbridge_id: null
    };
  }
}

function serializeShape(shape) {
  return {
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
    fill: shapeFill(shape),
    ...flexSnapshot(shape),
    ...componentMetadata(shape)
  };
}

function serializeSelection() {
  return (penpot.selection || []).map(serializeShape);
}

function sendSelection() {
  penpot.ui.sendMessage({
    type: "designbridge:selection",
    selection: serializeSelection()
  });
}

function sendContext() {
  const rawRevision = penpot.currentFile?.getPluginData("designbridge:revision") || null;
  const revision = rawRevision ? Number(rawRevision) : null;
  penpot.ui.sendMessage({
    type: "designbridge:context",
    project_id: penpot.currentFile?.getPluginData("designbridge:document-id") || null,
    revision: Number.isFinite(revision) ? revision : null,
    file_name: penpot.currentFile?.name || null,
    page_name: penpot.currentPage?.name || null
  });
}

penpot.on("selectionchange", () => sendSelection());
sendContext();
sendSelection();
