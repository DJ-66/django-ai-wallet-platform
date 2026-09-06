import e from "typescript";

import i from "node:v8";

import r from "node:vm";

import { getSchemaNamesFromConfig as n } from "@gql.tada/internal";

import { findAllCallExpressions as o } from "@0no-co/graphqlsp/api";

import { e as t } from "./index-chunk2.mjs";

import { h as a } from "./scan-chunk.mjs";

import { p as s } from "./index-chunk.mjs";

var l = 262144e4;

function shouldScanFile(e) {
  if (e.endsWith(".d.ts") || e.endsWith(".d.mts") || e.endsWith(".d.cts")) {
    return !1;
  }
  return !/(^|[/\\])node_modules([/\\]|$)/.test(e);
}

var c;

function forceGc() {
  if (void 0 === c) {
    var e = globalThis.gc;
    if ("function" == typeof e) {
      c = e;
    } else {
      try {
        i.setFlagsFromString("--expose-gc");
        c = r.runInNewContext("gc");
        i.setFlagsFromString("--no-expose-gc");
      } catch {
        c = null;
      }
    }
  }
  if (c) {
    c();
  }
}

var f = t((async function* _runScan(i) {
  var r = n(i.pluginConfig);
  var t = s(i);
  var c = t.createExternalFiles();
  if (c.length) {
    yield {
      kind: "EXTERNAL_WARNING"
    };
    await t.addVirtualFiles(c);
  }
  var f = t.build();
  var m = f.buildPluginInfo(i.pluginConfig);
  var u = t.rootFileNames.filter(shouldScanFile);
  yield {
    kind: "FILE_COUNT",
    fileCount: u.length
  };
  var processSourceFile = (i, n, s) => {
    var l = i.fileName;
    var c = [];
    var f = [];
    var m = function collectModuleImports(i, r) {
      var n = [];
      for (var o of i.statements) {
        if (e.isImportDeclaration(o) && e.isStringLiteral(o.moduleSpecifier)) {
          var t = r(o.moduleSpecifier.text, i.fileName);
          if (t && shouldScanFile(t)) {
            n.push(t);
          }
        }
      }
      return n;
    }(i, t.resolveModulePath.bind(t));
    if (!a(i)) {
      return {
        filePath: l,
        documents: c,
        imports: m,
        warnings: f
      };
    }
    var u = o(i, s, {
      searchExternal: !1,
      collectFragments: !1
    }).nodes;
    for (var d of u) {
      var h = d.node.parent;
      if (!e.isCallExpression(h)) {
        continue;
      }
      var p = n.getSourcePosition(i, h.getStart());
      l = p.fileName;
      if (!r.has(d.schema)) {
        f.push({
          message: d.schema ? `The '${d.schema}' schema is not in the configuration but was referenced by a document.` : r.size > 1 ? "The document is not for a known schema. Have you re-generated the output file?" : "Multiple schemas are configured, but the document is not for a specific schema.",
          file: p.fileName,
          line: p.line,
          col: p.col
        });
        continue;
      }
      c.push({
        schemaName: d.schema,
        document: d.node.text,
        filePath: p.fileName,
        line: p.line,
        col: p.col
      });
    }
    return {
      filePath: l,
      documents: c,
      imports: m,
      warnings: f
    };
  };
  var isHeapOverSoftLimit = () => {
    if (process.memoryUsage().heapUsed < l) {
      return !1;
    }
    forceGc();
    return process.memoryUsage().heapUsed >= l;
  };
  var d = 0;
  for (var h of u) {
    if (d > 0 && (d >= 1e3 || isHeapOverSoftLimit())) {
      m = (f = t.build()).buildPluginInfo(i.pluginConfig);
      forceGc();
      d = 0;
    }
    var p = f.getSourceFile(h);
    if (!p) {
      continue;
    }
    var {filePath: g, documents: v, imports: F, warnings: N} = processSourceFile(p, f, m);
    d++;
    yield {
      kind: "FILE_SCAN",
      filePath: g,
      documents: v,
      imports: F,
      warnings: N
    };
  }
}));

export { f as runScan };
//# sourceMappingURL=thread-chunk3.mjs.map
