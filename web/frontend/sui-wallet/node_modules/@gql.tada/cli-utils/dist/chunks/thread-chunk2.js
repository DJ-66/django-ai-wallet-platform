var e = require("typescript");

var r = require("node:v8");

var a = require("node:vm");

var t = require("node:fs");

var i = require("node:path");

var n = require("node:crypto");

var o = require("@gql.tada/internal");

var s = require("@0no-co/graphqlsp/api");

var u = require("./index-chunk2.js");

var l = require("./scan-chunk.js");

var c = require("./index-chunk.js");

function _interopNamespaceDefault(e) {
  var r = Object.create(null);
  if (e) {
    Object.keys(e).forEach((function(a) {
      if ("default" !== a) {
        var t = Object.getOwnPropertyDescriptor(e, a);
        Object.defineProperty(r, a, t.get ? t : {
          enumerable: !0,
          get: function() {
            return e[a];
          }
        });
      }
    }));
  }
  r.default = e;
  return r;
}

var p = _interopNamespaceDefault(t);

var f = _interopNamespaceDefault(i);

var d = _interopNamespaceDefault(n);

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

var v = "turbo-document-hash-v1";

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
    var n = getFragmentHashes(a.arguments[1], t);
    if (!n) {
      return {
        hashable: !1
      };
    }
    var o = d.createHash("sha256");
    addHashPart(o, v);
    addHashPart(o, t || "");
    addHashPart(o, r.schemaFingerprints.get(t) || "");
    addHashPart(o, i);
    for (var s of n) {
      addHashPart(o, s);
    }
    return {
      hashable: !0,
      documentHash: `sha256:${o.digest("hex").slice(0, 32)}`
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

function collectImportsFromSourceFile(r, a, t, i, n, o, s) {
  var u = [];
  var l = function getTadaOutputPaths(e, r) {
    var a = [];
    if ("schema" in e && e.tadaOutputLocation) {
      a.push(f.resolve(r, e.tadaOutputLocation));
    } else if ("schemas" in e) {
      for (var t of e.schemas) {
        if (t.tadaOutputLocation) {
          a.push(f.resolve(r, t.tadaOutputLocation));
        }
      }
    }
    return a;
  }(a, n);
  for (var c of r.statements) {
    if (e.isImportDeclaration(c) && e.isStringLiteral(c.moduleSpecifier)) {
      var p = c.moduleSpecifier.text;
      if (!isTadaImport(p, r.fileName, l, i)) {
        var d = c.getFullText().trim();
        if (o) {
          var m = t(p, r.fileName, o);
          if (s) {
            if (m.endsWith(".ts") || m.endsWith(".tsx")) {
              m = m.replace(/\.ts$/, ".js").replace(/\.tsx$/, ".js");
            }
          } else {
            m = m.replace(/\.ts$/, "").replace(/\.tsx$/, "");
          }
          if (m && !m.includes("gql.tada")) {
            u.push({
              specifier: m,
              importClause: d.replace(p, m)
            });
          }
        } else {
          u.push({
            specifier: p,
            importClause: d
          });
        }
      }
    }
  }
  return u;
}

function isTadaImport(e, r, a, t) {
  var i = t(e, r);
  if (i) {
    return a.some((e => i === e));
  }
  if (e.startsWith(".")) {
    var n = f.dirname(r);
    var o = f.resolve(n, e);
    return a.some((e => o === e));
  }
  return a.some((r => e === r || e.startsWith(r + "/")));
}

async function* _runTurbo(r) {
  var a = o.getSchemaNamesFromConfig(r.pluginConfig);
  var t = c.programFactory(r);
  var i = new Map;
  var getCachedDocuments = a => {
    var t = getTurboOutputPath(r.turboOutputPath, a);
    if (!t) {
      return new Map;
    }
    var n = i.get(t);
    if (!n) {
      n = function readCachedTurboDocuments(r) {
        var a = new Map;
        if (!r || !p.existsSync(r)) {
          return a;
        }
        var t;
        try {
          t = p.readFileSync(r, "utf8");
        } catch {
          return a;
        }
        var i = e.createSourceFile(r, t, e.ScriptTarget.Latest, !0, e.ScriptKind.TS);
        var visit = r => {
          if (e.isInterfaceDeclaration(r) && "setupCache" === r.name.text) {
            for (var n of r.members) {
              if (!e.isPropertySignature(n) || !n.type) {
                continue;
              }
              if (!e.isStringLiteral(n.name) && !e.isNumericLiteral(n.name)) {
                continue;
              }
              var o = getHashComment(t, n);
              if (!o) {
                continue;
              }
              a.set(JSON.stringify(n.name.text), {
                documentHash: o,
                documentType: n.type.getText(i)
              });
            }
          }
          e.forEachChild(r, visit);
        };
        visit(i);
        return a;
      }(t);
      i.set(t, n);
    }
    return n;
  };
  t.addSourceFile({
    fileId: "__gql-tada-override__.d.ts",
    sourceText: T,
    scriptKind: e.ScriptKind.TS
  });
  var n = t.createExternalFiles();
  if (n.length) {
    yield {
      kind: "EXTERNAL_WARNING"
    };
    await t.addVirtualFiles(n);
  }
  var u = t.build();
  var d = u.buildPluginInfo(r.pluginConfig);
  var m = new Set(function getTurboOutputPaths(e) {
    return "string" == typeof e ? [ e ] : e.map((e => e.path));
  }(r.turboOutputPath).map((e => f.resolve(e))));
  var v = t.rootFileNames.filter((e => l.shouldScanTurboFile(e, m)));
  yield {
    kind: "FILE_COUNT",
    fileCount: v.length
  };
  var g = new Map;
  var y = {
    traces: new Map,
    host: void 0,
    resolutionCache: void 0
  };
  var processSourceFile = (i, n, o, u) => {
    var c = i.fileName;
    var p = [];
    var f = [];
    if (!l.hasGraphQLDocumentCandidate(i)) {
      return {
        filePath: c,
        documents: p,
        warnings: f
      };
    }
    var d = s.findAllCallExpressions(i, o, {
      searchExternal: !1,
      collectFragments: !1
    }).nodes;
    for (var m of d) {
      var v = m.node.parent;
      if (!e.isCallExpression(v)) {
        continue;
      }
      var h = n.getSourcePosition(i, v.getStart());
      c = h.fileName;
      if (!a.has(m.schema)) {
        f.push({
          message: m.schema ? `The '${m.schema}' schema is not in the configuration but was referenced by document.` : a.size > 1 ? "The document is not for a known schema. Have you re-generated the output file?" : "Multiple schemas are configured, but the document is not for a specific schema.",
          file: h.fileName,
          line: h.line,
          col: h.col
        });
        continue;
      }
      var T = traceCallToImportSource(v, i, n.program, y);
      if (T && !g.has(T)) {
        var F = n.program.getSourceFile(T);
        if (F) {
          var b = getTurboOutputPath(r.turboOutputPath, m.schema);
          var C = collectImportsFromSourceFile(F, r.pluginConfig, t.resolveModuleName.bind(t), t.resolveModulePath.bind(t), r.rootPath, b, !!t.wasOriginallyNodeNext);
          g.set(T, {
            absolutePath: T,
            imports: C
          });
        }
      }
      var N = JSON.stringify(m.node.text);
      var P = x.hashCallExpression(v, m.schema);
      var w = P.hashable && P.documentHash ? getCachedDocuments(m.schema).get(N) : void 0;
      var E = void 0;
      var O = !1;
      if (w && w.documentHash === P.documentHash) {
        E = w.documentType;
        O = !0;
      } else {
        var H = u.getTypeAtLocation(v);
        if (!H.symbol || "TadaDocumentNode" !== H.symbol.getEscapedName()) {
          f.push({
            message: 'The discovered document is not of type "TadaDocumentNode".\nIf this is unexpected, please file an issue describing your case.',
            file: h.fileName,
            line: h.line,
            col: h.col
          });
          continue;
        }
        E = u.typeToString(H, v, S);
      }
      p.push({
        schemaName: m.schema,
        argumentKey: N,
        documentType: E,
        documentHash: P.documentHash,
        isCached: O
      });
    }
    return {
      filePath: c,
      documents: p,
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
  var F = u.program.getTypeChecker();
  var x = createDocumentHasher({
    get checker() {
      return F;
    },
    schemaFingerprints: computeSchemaFingerprints(r)
  });
  var b = 0;
  for (var C of v) {
    if (b > 0 && (b >= 1e3 || isHeapOverSoftLimit())) {
      d = (u = t.build()).buildPluginInfo(r.pluginConfig);
      forceGc();
      F = u.program.getTypeChecker();
      b = 0;
    }
    var N = u.getSourceFile(C);
    if (!N) {
      continue;
    }
    var {filePath: P, documents: w, warnings: E} = processSourceFile(N, u, d, F);
    b++;
    yield {
      kind: "FILE_TURBO",
      filePath: P,
      documents: w,
      warnings: E
    };
  }
  if (g.size > 0) {
    yield {
      kind: "GRAPHQL_SOURCES",
      sources: Array.from(g.values())
    };
  }
}

function computeSchemaFingerprints(e) {
  var r = new Map;
  var a = f.dirname(e.configPath);
  for (var t of o.getSchemaNamesFromConfig(e.pluginConfig)) {
    var i = o.getSchemaConfigForName(e.pluginConfig, t || void 0);
    var n = i && i.tadaOutputLocation;
    if (!n) {
      continue;
    }
    var s = void 0;
    try {
      s = p.readFileSync(f.resolve(a, n), "utf8");
    } catch {
      continue;
    }
    var u = d.createHash("sha256").update(s).digest("hex");
    r.set(t, `sha256:${u.slice(0, 32)}`);
  }
  return r;
}

function getTurboOutputPath(e, r) {
  if ("string" == typeof e) {
    return e;
  }
  return e.find((e => e.schemaName === r))?.path;
}

var g;

function forceGc() {
  if (void 0 === g) {
    var e = globalThis.gc;
    if ("function" == typeof e) {
      g = e;
    } else {
      try {
        r.setFlagsFromString("--expose-gc");
        g = a.runInNewContext("gc");
        r.setFlagsFromString("--no-expose-gc");
      } catch {
        g = null;
      }
    }
  }
  if (g) {
    g();
  }
}

var y = u.expose(_runTurbo);

var S = e.TypeFormatFlags.NoTruncation | e.TypeFormatFlags.NoTypeReduction | e.TypeFormatFlags.InTypeAlias | e.TypeFormatFlags.UseFullyQualifiedType | e.TypeFormatFlags.GenerateNamesForShadowedTypeParams | e.TypeFormatFlags.UseAliasDefinedOutsideCurrentScope | e.TypeFormatFlags.AllowUniqueESSymbolType | e.TypeFormatFlags.WriteTypeArgumentsOfSignature;

var T = "\nimport * as _gqlTada from 'gql.tada';\ndeclare module 'gql.tada' {\n  interface setupCache {\n    readonly __cacheDisabled: true;\n  }\n}\n".trim();

exports._runTurbo = _runTurbo;

exports.collectImportsFromSourceFile = collectImportsFromSourceFile;

exports.runTurbo = y;
//# sourceMappingURL=thread-chunk2.js.map
