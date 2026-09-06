var e = require("typescript");

var i = require("@gql.tada/internal");

var r = require("@0no-co/graphqlsp/api");

var n = require("./index-chunk2.js");

var t = require("./index-chunk.js");

var a = "FragmentDefinition";

class GraphQLError extends Error {
  constructor(e, i, r, n, t, a, o) {
    if (super(e), this.name = "GraphQLError", this.message = e, t) {
      this.path = t;
    }
    if (i) {
      this.nodes = Array.isArray(i) ? i : [ i ];
    }
    if (r) {
      this.source = r;
    }
    if (n) {
      this.positions = n;
    }
    if (a) {
      this.originalError = a;
    }
    var s = o;
    if (!s && a) {
      var l = a.extensions;
      if (l && "object" == typeof l) {
        s = l;
      }
    }
    this.extensions = s || {};
  }
  toJSON() {
    return {
      ...this,
      message: this.message
    };
  }
  toString() {
    return this.message;
  }
  get [Symbol.toStringTag]() {
    return "GraphQLError";
  }
}

var o;

var s;

function error(e) {
  return new GraphQLError(`Syntax Error: Unexpected token at ${s} in ${e}`);
}

function advance(e) {
  if (e.lastIndex = s, e.test(o)) {
    return o.slice(s, s = e.lastIndex);
  }
}

var l = / +(?=[^\s])/y;

function blockString(e) {
  var i = e.split("\n");
  var r = "";
  var n = 0;
  var t = 0;
  var a = i.length - 1;
  for (var o = 0; o < i.length; o++) {
    if (l.lastIndex = 0, l.test(i[o])) {
      if (o && (!n || l.lastIndex < n)) {
        n = l.lastIndex;
      }
      t = t || o, a = o;
    }
  }
  for (var s = t; s <= a; s++) {
    if (s !== t) {
      r += "\n";
    }
    r += i[s].slice(n).replace(/\\"""/g, '"""');
  }
  return r;
}

function ignored() {
  for (var e = 0 | o.charCodeAt(s++); 9 === e || 10 === e || 13 === e || 32 === e || 35 === e || 44 === e || 65279 === e; e = 0 | o.charCodeAt(s++)) {
    if (35 === e) {
      for (;(e = 0 | o.charCodeAt(s++)) && 10 !== e && 13 !== e; ) {}
    }
  }
  s--;
}

function name() {
  var e = s;
  for (var i = 0 | o.charCodeAt(s++); i >= 48 && i <= 57 || i >= 65 && i <= 90 || 95 === i || i >= 97 && i <= 122; i = 0 | o.charCodeAt(s++)) {}
  if (e === s - 1) {
    throw error("Name");
  }
  var r = o.slice(e, --s);
  return ignored(), r;
}

function nameNode() {
  return {
    kind: "Name",
    value: name()
  };
}

var d = /(?:"""|(?:[\s\S]*?[^\\])""")/y;

var c = /(?:(?:\.\d+)?[eE][+-]?\d+|\.\d+)/y;

function value(e) {
  var i;
  switch (o.charCodeAt(s)) {
   case 91:
    s++, ignored();
    var r = [];
    for (;93 !== o.charCodeAt(s); ) {
      r.push(value(e));
    }
    return s++, ignored(), {
      kind: "ListValue",
      values: r
    };

   case 123:
    s++, ignored();
    var n = [];
    for (;125 !== o.charCodeAt(s); ) {
      var t = nameNode();
      if (58 !== o.charCodeAt(s++)) {
        throw error("ObjectField");
      }
      ignored(), n.push({
        kind: "ObjectField",
        name: t,
        value: value(e)
      });
    }
    return s++, ignored(), {
      kind: "ObjectValue",
      fields: n
    };

   case 36:
    if (e) {
      throw error("Variable");
    }
    return s++, {
      kind: "Variable",
      name: nameNode()
    };

   case 34:
    if (34 === o.charCodeAt(s + 1) && 34 === o.charCodeAt(s + 2)) {
      if (s += 3, null == (i = advance(d))) {
        throw error("StringValue");
      }
      return ignored(), {
        kind: "StringValue",
        value: blockString(i.slice(0, -3)),
        block: !0
      };
    } else {
      var a = s;
      var l;
      s++;
      var u = !1;
      for (l = 0 | o.charCodeAt(s++); 92 === l && (s++, u = !0) || 10 !== l && 13 !== l && 34 !== l && l; l = 0 | o.charCodeAt(s++)) {}
      if (34 !== l) {
        throw error("StringValue");
      }
      return i = o.slice(a, s), ignored(), {
        kind: "StringValue",
        value: u ? JSON.parse(i) : i.slice(1, -1),
        block: !1
      };
    }

   case 45:
   case 48:
   case 49:
   case 50:
   case 51:
   case 52:
   case 53:
   case 54:
   case 55:
   case 56:
   case 57:
    var v = s++;
    var f;
    for (;(f = 0 | o.charCodeAt(s++)) >= 48 && f <= 57; ) {}
    var m = o.slice(v, --s);
    if (46 === (f = o.charCodeAt(s)) || 69 === f || 101 === f) {
      if (null == (i = advance(c))) {
        throw error("FloatValue");
      }
      return ignored(), {
        kind: "FloatValue",
        value: m + i
      };
    } else {
      return ignored(), {
        kind: "IntValue",
        value: m
      };
    }

   case 110:
    if (117 === o.charCodeAt(s + 1) && 108 === o.charCodeAt(s + 2) && 108 === o.charCodeAt(s + 3)) {
      return s += 4, ignored(), {
        kind: "NullValue"
      };
    } else {
      break;
    }

   case 116:
    if (114 === o.charCodeAt(s + 1) && 117 === o.charCodeAt(s + 2) && 101 === o.charCodeAt(s + 3)) {
      return s += 4, ignored(), {
        kind: "BooleanValue",
        value: !0
      };
    } else {
      break;
    }

   case 102:
    if (97 === o.charCodeAt(s + 1) && 108 === o.charCodeAt(s + 2) && 115 === o.charCodeAt(s + 3) && 101 === o.charCodeAt(s + 4)) {
      return s += 5, ignored(), {
        kind: "BooleanValue",
        value: !1
      };
    } else {
      break;
    }
  }
  return {
    kind: "EnumValue",
    value: name()
  };
}

function arguments_(e) {
  if (40 === o.charCodeAt(s)) {
    var i = [];
    s++, ignored();
    do {
      var r = nameNode();
      if (58 !== o.charCodeAt(s++)) {
        throw error("Argument");
      }
      ignored(), i.push({
        kind: "Argument",
        name: r,
        value: value(e)
      });
    } while (41 !== o.charCodeAt(s));
    return s++, ignored(), i;
  }
}

function directives(e) {
  if (64 === o.charCodeAt(s)) {
    var i = [];
    do {
      s++, i.push({
        kind: "Directive",
        name: nameNode(),
        arguments: arguments_(e)
      });
    } while (64 === o.charCodeAt(s));
    return i;
  }
}

function type() {
  var e = 0;
  for (;91 === o.charCodeAt(s); ) {
    e++, s++, ignored();
  }
  var i = {
    kind: "NamedType",
    name: nameNode()
  };
  do {
    if (33 === o.charCodeAt(s)) {
      s++, ignored(), i = {
        kind: "NonNullType",
        type: i
      };
    }
    if (e) {
      if (93 !== o.charCodeAt(s++)) {
        throw error("NamedType");
      }
      ignored(), i = {
        kind: "ListType",
        type: i
      };
    }
  } while (e--);
  return i;
}

function selectionSetStart() {
  if (123 !== o.charCodeAt(s++)) {
    throw error("SelectionSet");
  }
  return ignored(), selectionSet();
}

function selectionSet() {
  var e = [];
  do {
    if (46 === o.charCodeAt(s)) {
      if (46 !== o.charCodeAt(++s) || 46 !== o.charCodeAt(++s)) {
        throw error("SelectionSet");
      }
      switch (s++, ignored(), o.charCodeAt(s)) {
       case 64:
        e.push({
          kind: "InlineFragment",
          typeCondition: void 0,
          directives: directives(!1),
          selectionSet: selectionSetStart()
        });
        break;

       case 111:
        if (110 === o.charCodeAt(s + 1)) {
          s += 2, ignored(), e.push({
            kind: "InlineFragment",
            typeCondition: {
              kind: "NamedType",
              name: nameNode()
            },
            directives: directives(!1),
            selectionSet: selectionSetStart()
          });
        } else {
          e.push({
            kind: "FragmentSpread",
            name: nameNode(),
            directives: directives(!1)
          });
        }
        break;

       case 123:
        s++, ignored(), e.push({
          kind: "InlineFragment",
          typeCondition: void 0,
          directives: void 0,
          selectionSet: selectionSet()
        });
        break;

       default:
        e.push({
          kind: "FragmentSpread",
          name: nameNode(),
          directives: directives(!1)
        });
      }
    } else {
      var i = nameNode();
      var r = void 0;
      if (58 === o.charCodeAt(s)) {
        s++, ignored(), r = i, i = nameNode();
      }
      var n = arguments_(!1);
      var t = directives(!1);
      var a = void 0;
      if (123 === o.charCodeAt(s)) {
        s++, ignored(), a = selectionSet();
      }
      e.push({
        kind: "Field",
        alias: r,
        name: i,
        arguments: n,
        directives: t,
        selectionSet: a
      });
    }
  } while (125 !== o.charCodeAt(s));
  return s++, ignored(), {
    kind: "SelectionSet",
    selections: e
  };
}

function variableDefinitions() {
  if (ignored(), 40 === o.charCodeAt(s)) {
    var e = [];
    s++, ignored();
    do {
      var i = void 0;
      if (34 === o.charCodeAt(s)) {
        i = value(!0);
      }
      if (36 !== o.charCodeAt(s++)) {
        throw error("Variable");
      }
      var r = nameNode();
      if (58 !== o.charCodeAt(s++)) {
        throw error("VariableDefinition");
      }
      ignored();
      var n = type();
      var t = void 0;
      if (61 === o.charCodeAt(s)) {
        s++, ignored(), t = value(!0);
      }
      ignored();
      var a = {
        kind: "VariableDefinition",
        variable: {
          kind: "Variable",
          name: r
        },
        type: n,
        defaultValue: t,
        directives: directives(!0)
      };
      if (i) {
        a.description = i;
      }
      e.push(a);
    } while (41 !== o.charCodeAt(s));
    return s++, ignored(), e;
  }
}

function fragmentDefinition(e) {
  var i = nameNode();
  if (111 !== o.charCodeAt(s++) || 110 !== o.charCodeAt(s++)) {
    throw error("FragmentDefinition");
  }
  ignored();
  var r = {
    kind: "FragmentDefinition",
    name: i,
    typeCondition: {
      kind: "NamedType",
      name: nameNode()
    },
    directives: directives(!1),
    selectionSet: selectionSetStart()
  };
  if (e) {
    r.description = e;
  }
  return r;
}

function definitions() {
  var e = [];
  do {
    var i = void 0;
    if (34 === o.charCodeAt(s)) {
      i = value(!0);
    }
    if (123 === o.charCodeAt(s)) {
      if (i) {
        throw error("Document");
      }
      s++, ignored(), e.push({
        kind: "OperationDefinition",
        operation: "query",
        name: void 0,
        variableDefinitions: void 0,
        directives: void 0,
        selectionSet: selectionSet()
      });
    } else {
      var r = name();
      switch (r) {
       case "fragment":
        e.push(fragmentDefinition(i));
        break;

       case "query":
       case "mutation":
       case "subscription":
        var n;
        var t = void 0;
        if (40 !== (n = o.charCodeAt(s)) && 64 !== n && 123 !== n) {
          t = nameNode();
        }
        var a = {
          kind: "OperationDefinition",
          operation: r,
          name: t,
          variableDefinitions: variableDefinitions(),
          directives: directives(!1),
          selectionSet: selectionSetStart()
        };
        if (i) {
          a.description = i;
        }
        e.push(a);
        break;

       default:
        throw error("Document");
      }
    }
  } while (s < o.length);
  return e;
}

function parse(e, i) {
  if (o = e.body ? e.body : e, s = 0, ignored(), i) {} else {
    return {
      kind: "Document",
      definitions: definitions(),
      loc: {
        start: 0,
        end: o.length,
        startToken: void 0,
        endToken: void 0,
        source: {
          body: o,
          name: "graphql.web",
          locationOffset: {
            line: 1,
            column: 1
          }
        }
      }
    };
  }
}

function mapJoin(e, i, r) {
  var n = "";
  for (var t = 0; t < e.length; t++) {
    if (t) {
      n += i;
    }
    n += r(e[t]);
  }
  return n;
}

var u = "\n";

var v = {
  OperationDefinition(e) {
    var i = "";
    if (e.description) {
      i += v.StringValue(e.description) + "\n";
    }
    if (i += e.operation, e.name) {
      i += " " + e.name.value;
    }
    if (e.variableDefinitions && e.variableDefinitions.length) {
      if (!e.name) {
        i += " ";
      }
      i += "(" + mapJoin(e.variableDefinitions, ", ", v.VariableDefinition) + ")";
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", v.Directive);
    }
    var r = v.SelectionSet(e.selectionSet);
    return "query" !== i ? i + " " + r : r;
  },
  VariableDefinition(e) {
    var i = "";
    if (e.description) {
      i += v.StringValue(e.description) + " ";
    }
    if (i += v.Variable(e.variable) + ": " + _print(e.type), e.defaultValue) {
      i += " = " + _print(e.defaultValue);
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", v.Directive);
    }
    return i;
  },
  Field(e) {
    var i = e.alias ? e.alias.value + ": " + e.name.value : e.name.value;
    if (e.arguments && e.arguments.length) {
      var r = mapJoin(e.arguments, ", ", v.Argument);
      if (i.length + r.length + 2 > 80) {
        i += "(" + (u += "  ") + mapJoin(e.arguments, u, v.Argument) + (u = u.slice(0, -2)) + ")";
      } else {
        i += "(" + r + ")";
      }
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", v.Directive);
    }
    if (e.selectionSet && e.selectionSet.selections.length) {
      i += " " + v.SelectionSet(e.selectionSet);
    }
    return i;
  },
  StringValue(e) {
    if (e.block) {
      return function printBlockString(e) {
        return '"""\n' + e.replace(/"""/g, '\\"""') + '\n"""';
      }(e.value).replace(/\n/g, u);
    } else {
      return function printString(e) {
        return JSON.stringify(e);
      }(e.value);
    }
  },
  BooleanValue: e => "" + e.value,
  NullValue: e => "null",
  IntValue: e => e.value,
  FloatValue: e => e.value,
  EnumValue: e => e.value,
  Name: e => e.value,
  Variable: e => "$" + e.name.value,
  ListValue: e => "[" + mapJoin(e.values, ", ", _print) + "]",
  ObjectValue: e => "{" + mapJoin(e.fields, ", ", v.ObjectField) + "}",
  ObjectField: e => e.name.value + ": " + _print(e.value),
  Document(e) {
    if (!e.definitions || !e.definitions.length) {
      return "";
    } else {
      return mapJoin(e.definitions, "\n\n", _print);
    }
  },
  SelectionSet: e => "{" + (u += "  ") + mapJoin(e.selections, u, _print) + (u = u.slice(0, -2)) + "}",
  Argument: e => e.name.value + ": " + _print(e.value),
  FragmentSpread(e) {
    var i = "..." + e.name.value;
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", v.Directive);
    }
    return i;
  },
  InlineFragment(e) {
    var i = "...";
    if (e.typeCondition) {
      i += " on " + e.typeCondition.name.value;
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", v.Directive);
    }
    return i + " " + v.SelectionSet(e.selectionSet);
  },
  FragmentDefinition(e) {
    var i = "";
    if (e.description) {
      i += v.StringValue(e.description) + "\n";
    }
    if (i += "fragment " + e.name.value, i += " on " + e.typeCondition.name.value, e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", v.Directive);
    }
    return i + " " + v.SelectionSet(e.selectionSet);
  },
  Directive(e) {
    var i = "@" + e.name.value;
    if (e.arguments && e.arguments.length) {
      i += "(" + mapJoin(e.arguments, ", ", v.Argument) + ")";
    }
    return i;
  },
  NamedType: e => e.name.value,
  ListType: e => "[" + _print(e.type) + "]",
  NonNullType: e => _print(e.type) + "!"
};

var _print = e => v[e.kind](e);

function print(e) {
  return u = "\n", v[e.kind] ? v[e.kind](e) : "";
}

var f = n.expose((async function* _runPersisted(n) {
  var o = i.getSchemaNamesFromConfig(n.pluginConfig);
  var s = t.programFactory(n);
  var l = s.createExternalFiles();
  if (l.length) {
    yield {
      kind: "EXTERNAL_WARNING"
    };
    await s.addVirtualFiles(l);
  }
  var d = s.build();
  var c = d.buildPluginInfo(n.pluginConfig);
  var u = d.getSourceFiles();
  yield {
    kind: "FILE_COUNT",
    fileCount: u.length
  };
  for (var v of u) {
    var f = v.fileName;
    var m = [];
    var h = [];
    var g = r.findAllPersistedCallExpressions(v, c);
    for (var p of g) {
      var S = d.getSourcePosition(v, p.node.getStart());
      f = S.fileName;
      if (!o.has(p.schema)) {
        h.push({
          message: p.schema ? `The '${p.schema}' schema is not in the configuration but was referenced by "graphql.persisted".` : o.size > 1 ? "The document is not for a known schema. Have you re-generated the output file?" : "Multiple schemas are configured, but the document is not for a specific schema.",
          file: S.fileName,
          line: S.line,
          col: S.col
        });
        continue;
      }
      var C = p.node.arguments[0];
      var A = p.node.arguments[1];
      var k = p.node.typeArguments && p.node.typeArguments[0];
      if (!C || !e.isStringLiteral(C)) {
        h.push({
          message: '"graphql.persisted" must be called with a string literal as the first argument.',
          file: S.fileName,
          line: S.line,
          col: S.col
        });
        continue;
      } else if (!A && !k) {
        h.push({
          message: '"graphql.persisted" is missing a document.\nThis may be passed as a generic such as `graphql.persisted<typeof document>` or as the second argument.',
          file: S.fileName,
          line: S.line,
          col: S.col
        });
        continue;
      }
      var y = null;
      var b = p.node;
      if (A && (e.isCallExpression(A) || e.isIdentifier(A))) {
        y = r.getDocumentReferenceFromDocumentNode(A, v.fileName, c).node;
        b = A;
      } else if (k && e.isTypeQueryNode(k)) {
        y = r.getDocumentReferenceFromTypeQuery(k, v.fileName, c).node;
        b = k;
      }
      if (!y) {
        h.push({
          message: `Could not find reference for "${b.getText()}".\nIf this is unexpected, please file an issue describing your case.`,
          file: S.fileName,
          line: S.line,
          col: S.col
        });
        continue;
      }
      if (!y || !e.isCallExpression(y) || !e.isNoSubstitutionTemplateLiteral(y.arguments[0]) && !e.isStringLiteral(y.arguments[0])) {
        h.push({
          message: `The referenced document of "${b.getText()}" contains no document string literal.\nIf this is unexpected, please file an issue describing your case.`,
          file: S.fileName,
          line: S.line,
          col: S.col
        });
        continue;
      }
      var N = [];
      var V = y.arguments[0].getText().slice(1, -1);
      if (y.arguments[1] && e.isArrayLiteralExpression(y.arguments[1])) {
        r.unrollTadaFragments(y.arguments[1], N, d.buildPluginInfo(n.pluginConfig));
      }
      var D = new Set;
      var w = void 0;
      if (n.disableNormalization) {
        w = V;
      } else {
        try {
          var F = parse(V);
          var T = new Set;
          for (var x of F.definitions) {
            if (x.kind === a && !T.has(x)) {
              stripUnmaskDirectivesFromDefinition(x);
            }
          }
          w = print(F);
        } catch (e) {
          h.push({
            message: `The referenced document of "${b.getText()}" could not be parsed.\nRun \`check\` to see specific validation errors.`,
            file: S.fileName,
            line: S.line,
            col: S.col
          });
          continue;
        }
      }
      for (var E of N) {
        stripUnmaskDirectivesFromDefinition(E);
        var I = print(E);
        if (!D.has(I)) {
          w += "\n\n" + print(E);
          D.add(I);
        }
      }
      m.push({
        schemaName: p.schema,
        hashKey: C.getText().slice(1, -1),
        document: w
      });
    }
    yield {
      kind: "FILE_PERSISTED",
      filePath: f,
      documents: m,
      warnings: h
    };
  }
}));

var stripUnmaskDirectivesFromDefinition = e => {
  e.directives = e.directives?.filter((e => "_unmask" !== e.name.value));
};

exports.runPersisted = f;
//# sourceMappingURL=thread-chunk.js.map
