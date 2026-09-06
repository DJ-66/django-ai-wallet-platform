import e from "typescript";

import r from "node:v8";

import a from "node:vm";

import * as t from "node:fs";

import * as i from "node:path";

import * as n from "node:crypto";

import { getSchemaNamesFromConfig as o, getSchemaConfigForName as s } from "@gql.tada/internal";

import { findAllCallExpressions as u } from "@0no-co/graphqlsp/api";

import { e as l } from "./index-chunk2.mjs";

import { s as c, h as p } from "./scan-chunk.mjs";

import { p as f } from "./index-chunk.mjs";

var m = /@gql\.tada\/hash\s+([^\s*]+)/;

function getHashComment(r, a) {
  var t = e.getLeadingCommentRanges(r, a.pos) || [];
  for (var i = t.length - 1; i >= 0; i--) {
    var n = r.slice(t[i].pos, t[i].end);
    var o = m.exec(n);
    if (o) {
      return o[1];
    }
  }
  return;
}

var d = "turbo-document-hash-v1";

function createDocumentHasher(r) {
  var a = new WeakMap;
  var t = new Map;
  var i = new WeakSet;
  var hashCallExpression = (e, r) => {
    var t = r || "";
    var n = a.get(e)?.get(t);
    if (n) {
      return n;
    } else if (i.has(e)) {
      return {
        hashable: !1
      };
    }
    i.add(e);
    var o = computeCallExpressionHash(e, r);
    i.delete(e);
    var s = a.get(e);
    if (!s) {
      s = new Map;
      a.set(e, s);
    }
    s.set(t, o);
    return o;
  };
  var computeCallExpressionHash = (a, t) => {
    var i = function getStaticStringValue(r) {
      if (!r) {
        return;
      }
      r = unwrapExpression(r);
      if (e.isStringLiteral(r) || e.isNoSubstitutionTemplateLiteral(r)) {
        return r.text;
      }
      return;
    }(a.arguments[0]);
    if (null == i) {
      return {
        hashable: !1
      };
    }
    var o = getFragmentHashes(a.arguments[1], t);
    if (!o) {
      return {
        hashable: !1
      };
    }
    var s = n.createHash("sha256");
    addHashPart(s, d);
    addHashPart(s, t || "");
    addHashPart(s, r.schemaFingerprints.get(t) || "");
    addHashPart(s, i);
    for (var u of o) {
      addHashPart(s, u);
    }
    return {
      hashable: !0,
      documentHash: `sha256:${s.digest("hex").slice(0, 32)}`
    };
  };
  var getFragmentHashes = (r, a) => {
    if (!r) {
      return [];
    }
    r = unwrapExpression(r);
    if (e.isArrayLiteralExpression(r)) {
      var t = [];
      for (var i of r.elements) {
        if (e.isSpreadElement(i)) {
          var n = getFragmentHashes(i.expression, a);
          if (!n) {
            return null;
          }
          t.push(...n);
          continue;
        }
        var o = resolveDocumentCallExpression(i);
        if (!o) {
          return null;
        }
        var s = hashCallExpression(o, a);
        if (!s.hashable || !s.documentHash) {
          return null;
        }
        t.push(s.documentHash);
      }
      return t;
    }
    var u = resolveDeclarationInitializer(r);
    if (u && u !== r) {
      return getFragmentHashes(u, a);
    }
    return null;
  };
  var resolveDocumentCallExpression = r => {
    r = unwrapExpression(r);
    if (e.isCallExpression(r)) {
      return r;
    }
    var a = getSymbol(r);
    if (!a) {
      return null;
    }
    var i = t.get(a);
    if (void 0 !== i) {
      return i;
    }
    var n = resolveSymbolCallExpression(a);
    t.set(a, n);
    return n;
  };
  var resolveDeclarationInitializer = r => {
    var a = getSymbol(r);
    if (!a) {
      return null;
    }
    for (var t of a.declarations || []) {
      if (e.isVariableDeclaration(t) && t.initializer) {
        return t.initializer;
      }
    }
    return null;
  };
  var resolveSymbolCallExpression = r => {
    for (var a of r.declarations || []) {
      if (e.isVariableDeclaration(a) && a.initializer) {
        var t = unwrapExpression(a.initializer);
        if (e.isCallExpression(t)) {
          return t;
        }
      }
    }
    return null;
  };
  var getSymbol = a => {
    var t = r.checker.getSymbolAtLocation(a);
    if (t && t.flags & e.SymbolFlags.Alias) {
      t = r.checker.getAliasedSymbol(t);
    }
    return t;
  };
  return {
    hashCallExpression
  };
}

function unwrapExpression(r) {
  while (e.isParenthesizedExpression(r) || e.isAsExpression(r) || e.isTypeAssertionExpression(r) || e.isSatisfiesExpression(r) || e.isNonNullExpression(r)) {
    r = r.expression;
  }
  return r;
}

function addHashPart(e, r) {
  e.update(`${r.length}:`);
  e.update(r);
  e.update("\0");
}

var h = 262144e4;

function traceCallToImportSource(r, a, t, i) {
  var n = r.expression;
  var o;
  if (e.isIdentifier(n)) {
    o = n;
  } else if (e.isPropertyAccessExpression(n) && e.isIdentifier(n.expression)) {
    o = n.expression;
  }
  if (!o) {
    return;
  }
  var s = `${a.fileName}\0${o.text}`;
  if (i.traces.has(s)) {
    return i.traces.get(s);
  }
  var u;
  var l = t.getTypeChecker().getSymbolAtLocation(o);
  if (l && l.declarations) {
    for (var c of l.declarations) {
      var p = findImportDeclaration(c);
      if (p && e.isStringLiteral(p.moduleSpecifier)) {
        u = resolveModulePath(p.moduleSpecifier.text, a, t, i);
        break;
      }
    }
  }
  i.traces.set(s, u);
  return u;
}

function findImportDeclaration(r) {
  var a = r;
  while (a) {
    if (e.isImportDeclaration(a)) {
      return a;
    }
    a = a.parent;
  }
  return;
}

function resolveModulePath(r, a, t, i) {
  var n = t.getCompilerOptions();
  var o = i.host || (i.host = e.createCompilerHost(n));
  var s = i.resolutionCache || (i.resolutionCache = e.createModuleResolutionCache(o.getCurrentDirectory(), o.getCanonicalFileName.bind(o), n));
  var u = e.resolveModuleName(r, a.fileName, n, o, s);
  if (u.resolvedModule) {
    return u.resolvedModule.resolvedFileName;
  }
  return;
}

function collectImportsFromSourceFile(r, a, t, n, o, s, u) {
  var l = [];
  var c = function getTadaOutputPaths(e, r) {
    var a = [];
    if ("schema" in e && e.tadaOutputLocation) {
      a.push(i.resolve(r, e.tadaOutputLocation));
    } else if ("schemas" in e) {
      for (var t of e.schemas) {
        if (t.tadaOutputLocation) {
          a.push(i.resolve(r, t.tadaOutputLocation));
        }
      }
    }
    return a;
  }(a, o);
  for (var p of r.statements) {
    if (e.isImportDeclaration(p) && e.isStringLiteral(p.moduleSpecifier)) {
      var f = p.moduleSpecifier.text;
      if (!isTadaImport(f, r.fileName, c, n)) {
        var m = p.getFullText().trim();
        if (s) {
          var d = t(f, r.fileName, s);
          if (u) {
            if (d.endsWith(".ts") || d.endsWith(".tsx")) {
              d = d.replace(/\.ts$/, ".js").replace(/\.tsx$/, ".js");
            }
          } else {
            d = d.replace(/\.ts$/, "").replace(/\.tsx$/, "");
          }
          if (d && !d.includes("gql.tada")) {
            l.push({
              specifier: d,
              importClause: m.replace(f, d)
            });
          }
        } else {
          l.push({
            specifier: f,
            importClause: m
          });
        }
      }
    }
  }
  return l;
}

function isTadaImport(e, r, a, t) {
  var n = t(e, r);
  if (n) {
    return a.some((e => n === e));
  }
  if (e.startsWith(".")) {
    var o = i.dirname(r);
    var s = i.resolve(o, e);
    return a.some((e => s === e));
  }
  return a.some((r => e === r || e.startsWith(r + "/")));
}

async function* _runTurbo(r) {
  var a = o(r.pluginConfig);
  var n = f(r);
  var s = new Map;
  var getCachedDocuments = a => {
    var i = getTurboOutputPath(r.turboOutputPath, a);
    if (!i) {
      return new Map;
    }
    var n = s.get(i);
    if (!n) {
      n = function readCachedTurboDocuments(r) {
        var a = new Map;
        if (!r || !t.existsSync(r)) {
          return a;
        }
        var i;
        try {
          i = t.readFileSync(r, "utf8");
        } catch {
          return a;
        }
        var n = e.createSourceFile(r, i, e.ScriptTarget.Latest, !0, e.ScriptKind.TS);
        var visit = r => {
          if (e.isInterfaceDeclaration(r) && "setupCache" === r.name.text) {
            for (var t of r.members) {
              if (!e.isPropertySignature(t) || !t.type) {
                continue;
              }
              if (!e.isStringLiteral(t.name) && !e.isNumericLiteral(t.name)) {
                continue;
              }
              var o = getHashComment(i, t);
              if (!o) {
                continue;
              }
              a.set(JSON.stringify(t.name.text), {
                documentHash: o,
                documentType: t.type.getText(n)
              });
            }
          }
          e.forEachChild(r, visit);
        };
        visit(n);
        return a;
      }(i);
      s.set(i, n);
    }
    return n;
  };
  n.addSourceFile({
    fileId: "__gql-tada-override__.d.ts",
    sourceText: T,
    scriptKind: e.ScriptKind.TS
  });
  var l = n.createExternalFiles();
  if (l.length) {
    yield {
      kind: "EXTERNAL_WARNING"
    };
    await n.addVirtualFiles(l);
  }
  var m = n.build();
  var d = m.buildPluginInfo(r.pluginConfig);
  var v = new Set(function getTurboOutputPaths(e) {
    return "string" == typeof e ? [ e ] : e.map((e => e.path));
  }(r.turboOutputPath).map((e => i.resolve(e))));
  var g = n.rootFileNames.filter((e => c(e, v)));
  yield {
    kind: "FILE_COUNT",
    fileCount: g.length
  };
  var S = new Map;
  var x = {
    traces: new Map,
    host: void 0,
    resolutionCache: void 0
  };
  var processSourceFile = (t, i, o, s) => {
    var l = t.fileName;
    var c = [];
    var f = [];
    if (!p(t)) {
      return {
        filePath: l,
        documents: c,
        warnings: f
      };
    }
    var m = u(t, o, {
      searchExternal: !1,
      collectFragments: !1
    }).nodes;
    for (var d of m) {
      var h = d.node.parent;
      if (!e.isCallExpression(h)) {
        continue;
      }
      var v = i.getSourcePosition(t, h.getStart());
      l = v.fileName;
      if (!a.has(d.schema)) {
        f.push({
          message: d.schema ? `The '${d.schema}' schema is not in the configuration but was referenced by document.` : a.size > 1 ? "The document is not for a known schema. Have you re-generated the output file?" : "Multiple schemas are configured, but the document is not for a specific schema.",
          file: v.fileName,
          line: v.line,
          col: v.col
        });
        continue;
      }
      var g = traceCallToImportSource(h, t, i.program, x);
      if (g && !S.has(g)) {
        var T = i.program.getSourceFile(g);
        if (T) {
          var F = getTurboOutputPath(r.turboOutputPath, d.schema);
          var C = collectImportsFromSourceFile(T, r.pluginConfig, n.resolveModuleName.bind(n), n.resolveModulePath.bind(n), r.rootPath, F, !!n.wasOriginallyNodeNext);
          S.set(g, {
            absolutePath: g,
            imports: C
          });
        }
      }
      var N = JSON.stringify(d.node.text);
      var P = b.hashCallExpression(h, d.schema);
      var w = P.hashable && P.documentHash ? getCachedDocuments(d.schema).get(N) : void 0;
      var E = void 0;
      var H = !1;
      if (w && w.documentHash === P.documentHash) {
        E = w.documentType;
        H = !0;
      } else {
        var I = s.getTypeAtLocation(h);
        if (!I.symbol || "TadaDocumentNode" !== I.symbol.getEscapedName()) {
          f.push({
            message: 'The discovered document is not of type "TadaDocumentNode".\nIf this is unexpected, please file an issue describing your case.',
            file: v.fileName,
            line: v.line,
            col: v.col
          });
          continue;
        }
        E = s.typeToString(I, h, y);
      }
      c.push({
        schemaName: d.schema,
        argumentKey: N,
        documentType: E,
        documentHash: P.documentHash,
        isCached: H
      });
    }
    return {
      filePath: l,
      documents: c,
      warnings: f
    };
  };
  var isHeapOverSoftLimit = () => {
    if (process.memoryUsage().heapUsed < h) {
      return !1;
    }
    forceGc();
    return process.memoryUsage().heapUsed >= h;
  };
  var F = m.program.getTypeChecker();
  var b = createDocumentHasher({
    get checker() {
      return F;
    },
    schemaFingerprints: computeSchemaFingerprints(r)
  });
  var C = 0;
  for (var N of g) {
    if (C > 0 && (C >= 1e3 || isHeapOverSoftLimit())) {
      d = (m = n.build()).buildPluginInfo(r.pluginConfig);
      forceGc();
      F = m.program.getTypeChecker();
      C = 0;
    }
    var P = m.getSourceFile(N);
    if (!P) {
      continue;
    }
    var {filePath: w, documents: E, warnings: H} = processSourceFile(P, m, d, F);
    C++;
    yield {
      kind: "FILE_TURBO",
      filePath: w,
      documents: E,
      warnings: H
    };
  }
  if (S.size > 0) {
    yield {
      kind: "GRAPHQL_SOURCES",
      sources: Array.from(S.values())
    };
  }
}

function computeSchemaFingerprints(e) {
  var r = new Map;
  var a = i.dirname(e.configPath);
  for (var u of o(e.pluginConfig)) {
    var l = s(e.pluginConfig, u || void 0);
    var c = l && l.tadaOutputLocation;
    if (!c) {
      continue;
    }
    var p = void 0;
    try {
      p = t.readFileSync(i.resolve(a, c), "utf8");
    } catch {
      continue;
    }
    var f = n.createHash("sha256").update(p).digest("hex");
    r.set(u, `sha256:${f.slice(0, 32)}`);
  }
  return r;
}

function getTurboOutputPath(e, r) {
  if ("string" == typeof e) {
    return e;
  }
  return e.find((e => e.schemaName === r))?.path;
}

var v;

function forceGc() {
  if (void 0 === v) {
    var e = globalThis.gc;
    if ("function" == typeof e) {
      v = e;
    } else {
      try {
        r.setFlagsFromString("--expose-gc");
        v = a.runInNewContext("gc");
        r.setFlagsFromString("--no-expose-gc");
      } catch {
        v = null;
      }
    }
  }
  if (v) {
    v();
  }
}

var g = l(_runTurbo);

var y = e.TypeFormatFlags.NoTruncation | e.TypeFormatFlags.NoTypeReduction | e.TypeFormatFlags.InTypeAlias | e.TypeFormatFlags.UseFullyQualifiedType | e.TypeFormatFlags.GenerateNamesForShadowedTypeParams | e.TypeFormatFlags.UseAliasDefinedOutsideCurrentScope | e.TypeFormatFlags.AllowUniqueESSymbolType | e.TypeFormatFlags.WriteTypeArgumentsOfSignature;

var T = "\nimport * as _gqlTada from 'gql.tada';\ndeclare module 'gql.tada' {\n  interface setupCache {\n    readonly __cacheDisabled: true;\n  }\n}\n".trim();

export { _runTurbo, collectImportsFromSourceFile, g as runTurbo };
//# sourceMappingURL=thread-chunk2.mjs.map
