#!/usr/bin/env node

import { extractRDF } from "wrx";

const [url] = process.argv.slice(2);

if (!url) {
  console.error("Missing URL argument");
  process.exit(1);
}

try {
  const result = await extractRDF(url);

  if (!result) {
    console.log(JSON.stringify({
      ok: false,
      url,
      reason: "No RDF extracted",
    }));
    process.exit(0);
  }

  console.log(JSON.stringify({
    ok: true,
    url: result.url ?? url,
    source: result.source ?? "",
    format: result.format ?? "",
    content: result.content ?? "",
  }));
} catch (err) {
  const message = err instanceof Error ? err.message : String(err);
  console.error(`wrx extraction failed: ${message}`);
  process.exit(1);
}
