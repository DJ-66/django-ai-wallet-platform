var e = require("typescript");

var r = require("node:v8");

var i = require("node:vm");

var n = require("@gql.tada/internal");

var a = require("@0no-co/graphqlsp/api");

var t = require("./index-chunk2.js");

var o = require("./scan-chunk.js");

var s = require("./index-chunk.js");

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
        r.setFlagsFromString("--expose-gc");
        c = i.runInNewContext("gc");
        r.setFlagsFromString("--no-expose-gc");
      } catch {
        c = null;
      }
    }
  }
  if (c) {
    c();
  }
}

var u = t.expose((async function* _runScan(r) {
  var i = n.getSchemaNamesFromConfig(r.pluginConfig);
  var t = s.programFactory(r);
  var c = t.createExternalFiles();
  if (c.length) {
    yield {
      kind: "EXTERNAL_WARNING"
    };
    await t.addVirtualFiles(c);
  }
  var u = t.build();
  var f = u.buildPluginInfo(r.pluginConfig);
  var d = t.rootFileNames.filter(shouldScanFile);
  yield {
    kind: "FILE_COUNT",
    fileCount: d.length
  };
  var processSourceFile = (r, n, s) => {
    var l = r.fileName;
    var c = [];
    var u = [];
    var f = function collectModuleImports(r, i) {
      var n = [];
      for (var a of r.statements) {
        if (e.isImportDeclaration(a) && e.isStringLiteral(a.moduleSpecifier)) {
          var t = i(a.moduleSpecifier.text, r.fileName);
          if (t && shouldScanFile(t)) {
            n.push(t);
          }
        }
      }
      return n;
    }(r, t.resolveModulePath.bind(t));
    if (!o.hasGraphQLDocumentCandidate(r)) {
      return {
        filePath: l,
        documents: c,
        imports: f,
        warnings: u
      };
    }
    var d = a.findAllCallExpressions(r, s, {
      searchExternal: !1,
      collectFragments: !1
    }).nodes;
    for (var m of d) {
      var h = m.node.parent;
      if (!e.isCallExpression(h)) {
        continue;
      }
      var v = n.getSourcePosition(r, h.getStart());
      l = v.fileName;
      if (!i.has(m.schema)) {
        u.push({
          message: m.schema ? `The '${m.schema}' schema is not in the configuration but was referenced by a document.` : i.size > 1 ? "The document is not for a known schema. Have you re-generated the output file?" : "Multiple schemas are configured, but the document is not for a specific schema.",
          file: v.fileName,
          line: v.line,
          col: v.col
        });
        continue;
      }
      c.push({
        schemaName: m.schema,
        document: m.node.text,
        filePath: v.fileName,
        line: v.line,
        col: v.col
      });
    }
    return {
      filePath: l,
      documents: c,
      imports: f,
      warnings: u
    };
  };
  var isHeapOverSoftLimit = () => {
    if (process.memoryUsage().heapUsed < l) {
      return !1;
    }
    forceGc();
    return process.memoryUsage().heapUsed >= l;
  };
  var m = 0;
  for (var h of d) {
    if (m > 0 && (m >= 1e3 || isHeapOverSoftLimit())) {
      f = (u = t.build()).buildPluginInfo(r.pluginConfig);
      forceGc();
      m = 0;
    }
    var v = u.getSourceFile(h);
    if (!v) {
      continue;
    }
    var {filePath: g, documents: p, imports: F, warnings: S} = processSourceFile(v, u, f);
    m++;
    yield {
      kind: "FILE_SCAN",
      filePath: g,
      documents: p,
      imports: F,
      warnings: S
    };
  }
}));

exports.runScan = u;
//# sourceMappingURL=thread-chunk3.js.map
