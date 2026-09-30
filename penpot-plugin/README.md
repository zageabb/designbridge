# DesignBridge Penpot Importer

The plugin imports a DesignBridge `.designbridge.json` document into the active Penpot file as native editable objects.

## Local test

Serve the `public` directory:

```bash
cd penpot-plugin/public
python3 -m http.server 4400
```

Then open Penpot's Plugin Manager and install:

```text
http://localhost:4400/manifest.json
```

The importer accepts pasted JSON or a local JSON file.

## Current mapping

| DesignBridge | Penpot |
|---|---|
| page | Page |
| frame | Board |
| rectangle | Rectangle |
| text | Text |
| layout.direction | FlexLayout.dir |
| layout.gap | rowGap/columnGap |
| layout.padding | vertical/horizontal padding |
| layout.align | alignItems |

Each generated shape stores `designbridge:id` and `designbridge:type` as plugin data for future round-trip updates.

## Current limitations

v0.1 is a proof of the canonical-model path. Components/instances, token-library mapping, typography properties, images, constraints and update-in-place are the next slices.
