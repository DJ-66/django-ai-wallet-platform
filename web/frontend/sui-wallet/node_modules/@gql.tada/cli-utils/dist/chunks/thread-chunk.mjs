import e from "typescript";

import { getSchemaNamesFromConfig as i } from "@gql.tada/internal";

import { findAllPersistedCallExpressions as r, getDocumentReferenceFromDocumentNode as n, getDocumentReferenceFromTypeQuery as t, unrollTadaFragments as a } from "@0no-co/graphqlsp/api";

import { e as o } from "./index-chunk2.mjs";

import { p as s } from "./index-chunk.mjs";

var l = "FragmentDefinition";

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

var d;

var c;

function error(e) {
  return new GraphQLError(`Syntax Error: Unexpected token at ${c} in ${e}`);
}

function advance(e) {
  if (e.lastIndex = c, e.test(d)) {
    return d.slice(c, c = e.lastIndex);
  }
}

var u = / +(?=[^\s])/y;

function blockString(e) {
  var i = e.split("\n");
  var r = "";
  var n = 0;
  var t = 0;
  var a = i.length - 1;
  for (var o = 0; o < i.length; o++) {
    if (u.lastIndex = 0, u.test(i[o])) {
      if (o && (!n || u.lastIndex < n)) {
        n = u.lastIndex;
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
  for (var e = 0 | d.charCodeAt(c++); 9 === e || 10 === e || 13 === e || 32 === e || 35 === e || 44 === e || 65279 === e; e = 0 | d.charCodeAt(c++)) {
    if (35 === e) {
      for (;(e = 0 | d.charCodeAt(c++)) && 10 !== e && 13 !== e; ) {}
    }
  }
  c--;
}

function name() {
  var e = c;
  for (var i = 0 | d.charCodeAt(c++); i >= 48 && i <= 57 || i >= 65 && i <= 90 || 95 === i || i >= 97 && i <= 122; i = 0 | d.charCodeAt(c++)) {}
  if (e === c - 1) {
    throw error("Name");
  }
  var r = d.slice(e, --c);
  return ignored(), r;
}

function nameNode() {
  return {
    kind: "Name",
    value: name()
  };
}

var f = /(?:"""|(?:[\s\S]*?[^\\])""")/y;

var v = /(?:(?:\.\d+)?[eE][+-]?\d+|\.\d+)/y;

function value(e) {
  var i;
  switch (d.charCodeAt(c)) {
   case 91:
    c++, ignored();
    var r = [];
    for (;93 !== d.charCodeAt(c); ) {
      r.push(value(e));
    }
    return c++, ignored(), {
      kind: "ListValue",
      values: r
    };

   case 123:
    c++, ignored();
    var n = [];
    for (;125 !== d.charCodeAt(c); ) {
      var t = nameNode();
      if (58 !== d.charCodeAt(c++)) {
        throw error("ObjectField");
      }
      ignored(), n.push({
        kind: "ObjectField",
        name: t,
        value: value(e)
      });
    }
    return c++, ignored(), {
      kind: "ObjectValue",
      fields: n
    };

   case 36:
    if (e) {
      throw error("Variable");
    }
    return c++, {
      kind: "Variable",
      name: nameNode()
    };

   case 34:
    if (34 === d.charCodeAt(c + 1) && 34 === d.charCodeAt(c + 2)) {
      if (c += 3, null == (i = advance(f))) {
        throw error("StringValue");
      }
      return ignored(), {
        kind: "StringValue",
        value: blockString(i.slice(0, -3)),
        block: !0
      };
    } else {
      var a = c;
      var o;
      c++;
      var s = !1;
      for (o = 0 | d.charCodeAt(c++); 92 === o && (c++, s = !0) || 10 !== o && 13 !== o && 34 !== o && o; o = 0 | d.charCodeAt(c++)) {}
      if (34 !== o) {
        throw error("StringValue");
      }
      return i = d.slice(a, c), ignored(), {
        kind: "StringValue",
        value: s ? JSON.parse(i) : i.slice(1, -1),
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
    var l = c++;
    var u;
    for (;(u = 0 | d.charCodeAt(c++)) >= 48 && u <= 57; ) {}
    var m = d.slice(l, --c);
    if (46 === (u = d.charCodeAt(c)) || 69 === u || 101 === u) {
      if (null == (i = advance(v))) {
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
    if (117 === d.charCodeAt(c + 1) && 108 === d.charCodeAt(c + 2) && 108 === d.charCodeAt(c + 3)) {
      return c += 4, ignored(), {
        kind: "NullValue"
      };
    } else {
      break;
    }

   case 116:
    if (114 === d.charCodeAt(c + 1) && 117 === d.charCodeAt(c + 2) && 101 === d.charCodeAt(c + 3)) {
      return c += 4, ignored(), {
        kind: "BooleanValue",
        value: !0
      };
    } else {
      break;
    }

   case 102:
    if (97 === d.charCodeAt(c + 1) && 108 === d.charCodeAt(c + 2) && 115 === d.charCodeAt(c + 3) && 101 === d.charCodeAt(c + 4)) {
      return c += 5, ignored(), {
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
  if (40 === d.charCodeAt(c)) {
    var i = [];
    c++, ignored();
    do {
      var r = nameNode();
      if (58 !== d.charCodeAt(c++)) {
        throw error("Argument");
      }
      ignored(), i.push({
        kind: "Argument",
        name: r,
        value: value(e)
      });
    } while (41 !== d.charCodeAt(c));
    return c++, ignored(), i;
  }
}

function directives(e) {
  if (64 === d.charCodeAt(c)) {
    var i = [];
    do {
      c++, i.push({
        kind: "Directive",
        name: nameNode(),
        arguments: arguments_(e)
      });
    } while (64 === d.charCodeAt(c));
    return i;
  }
}

function type() {
  var e = 0;
  for (;91 === d.charCodeAt(c); ) {
    e++, c++, ignored();
  }
  var i = {
    kind: "NamedType",
    name: nameNode()
  };
  do {
    if (33 === d.charCodeAt(c)) {
      c++, ignored(), i = {
        kind: "NonNullType",
        type: i
      };
    }
    if (e) {
      if (93 !== d.charCodeAt(c++)) {
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
  if (123 !== d.charCodeAt(c++)) {
    throw error("SelectionSet");
  }
  return ignored(), selectionSet();
}

function selectionSet() {
  var e = [];
  do {
    if (46 === d.charCodeAt(c)) {
      if (46 !== d.charCodeAt(++c) || 46 !== d.charCodeAt(++c)) {
        throw error("SelectionSet");
      }
      switch (c++, ignored(), d.charCodeAt(c)) {
       case 64:
        e.push({
          kind: "InlineFragment",
          typeCondition: void 0,
          directives: directives(!1),
          selectionSet: selectionSetStart()
        });
        break;

       case 111:
        if (110 === d.charCodeAt(c + 1)) {
          c += 2, ignored(), e.push({
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
        c++, ignored(), e.push({
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
      if (58 === d.charCodeAt(c)) {
        c++, ignored(), r = i, i = nameNode();
      }
      var n = arguments_(!1);
      var t = directives(!1);
      var a = void 0;
      if (123 === d.charCodeAt(c)) {
        c++, ignored(), a = selectionSet();
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
  } while (125 !== d.charCodeAt(c));
  return c++, ignored(), {
    kind: "SelectionSet",
    selections: e
  };
}

function variableDefinitions() {
  if (ignored(), 40 === d.charCodeAt(c)) {
    var e = [];
    c++, ignored();
    do {
      var i = void 0;
      if (34 === d.charCodeAt(c)) {
        i = value(!0);
      }
      if (36 !== d.charCodeAt(c++)) {
        throw error("Variable");
      }
      var r = nameNode();
      if (58 !== d.charCodeAt(c++)) {
        throw error("VariableDefinition");
      }
      ignored();
      var n = type();
      var t = void 0;
      if (61 === d.charCodeAt(c)) {
        c++, ignored(), t = value(!0);
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
    } while (41 !== d.charCodeAt(c));
    return c++, ignored(), e;
  }
}

function fragmentDefinition(e) {
  var i = nameNode();
  if (111 !== d.charCodeAt(c++) || 110 !== d.charCodeAt(c++)) {
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
    if (34 === d.charCodeAt(c)) {
      i = value(!0);
    }
    if (123 === d.charCodeAt(c)) {
      if (i) {
        throw error("Document");
      }
      c++, ignored(), e.push({
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
        if (40 !== (n = d.charCodeAt(c)) && 64 !== n && 123 !== n) {
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
  } while (c < d.length);
  return e;
}

function parse(e, i) {
  if (d = e.body ? e.body : e, c = 0, ignored(), i) {} else {
    return {
      kind: "Document",
      definitions: definitions(),
      loc: {
        start: 0,
        end: d.length,
        startToken: void 0,
        endToken: void 0,
        source: {
          body: d,
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

var m = "\n";

var h = {
  OperationDefinition(e) {
    var i = "";
    if (e.description) {
      i += h.StringValue(e.description) + "\n";
    }
    if (i += e.operation, e.name) {
      i += " " + e.name.value;
    }
    if (e.variableDefinitions && e.variableDefinitions.length) {
      if (!e.name) {
        i += " ";
      }
      i += "(" + mapJoin(e.variableDefinitions, ", ", h.VariableDefinition) + ")";
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", h.Directive);
    }
    var r = h.SelectionSet(e.selectionSet);
    return "query" !== i ? i + " " + r : r;
  },
  VariableDefinition(e) {
    var i = "";
    if (e.description) {
      i += h.StringValue(e.description) + " ";
    }
    if (i += h.Variable(e.variable) + ": " + _print(e.type), e.defaultValue) {
      i += " = " + _print(e.defaultValue);
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", h.Directive);
    }
    return i;
  },
  Field(e) {
    var i = e.alias ? e.alias.value + ": " + e.name.value : e.name.value;
    if (e.arguments && e.arguments.length) {
      var r = mapJoin(e.arguments, ", ", h.Argument);
      if (i.length + r.length + 2 > 80) {
        i += "(" + (m += "  ") + mapJoin(e.arguments, m, h.Argument) + (m = m.slice(0, -2)) + ")";
      } else {
        i += "(" + r + ")";
      }
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", h.Directive);
    }
    if (e.selectionSet && e.selectionSet.selections.length) {
      i += " " + h.SelectionSet(e.selectionSet);
    }
    return i;
  },
  StringValue(e) {
    if (e.block) {
      return function printBlockString(e) {
        return '"""\n' + e.replace(/"""/g, '\\"""') + '\n"""';
      }(e.value).replace(/\n/g, m);
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
  ObjectValue: e => "{" + mapJoin(e.fields, ", ", h.ObjectField) + "}",
  ObjectField: e => e.name.value + ": " + _print(e.value),
  Document(e) {
    if (!e.definitions || !e.definitions.length) {
      return "";
    } else {
      return mapJoin(e.definitions, "\n\n", _print);
    }
  },
  SelectionSet: e => "{" + (m += "  ") + mapJoin(e.selections, m, _print) + (m = m.slice(0, -2)) + "}",
  Argument: e => e.name.value + ": " + _print(e.value),
  FragmentSpread(e) {
    var i = "..." + e.name.value;
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", h.Directive);
    }
    return i;
  },
  InlineFragment(e) {
    var i = "...";
    if (e.typeCondition) {
      i += " on " + e.typeCondition.name.value;
    }
    if (e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", h.Directive);
    }
    return i + " " + h.SelectionSet(e.selectionSet);
  },
  FragmentDefinition(e) {
    var i = "";
    if (e.description) {
      i += h.StringValue(e.description) + "\n";
    }
    if (i += "fragment " + e.name.value, i += " on " + e.typeCondition.name.value, e.directives && e.directives.length) {
      i += " " + mapJoin(e.directives, " ", h.Directive);
    }
    return i + " " + h.SelectionSet(e.selectionSet);
  },
  Directive(e) {
    var i = "@" + e.name.value;
    if (e.arguments && e.arguments.length) {
      i += "(" + mapJoin(e.arguments, ", ", h.Argument) + ")";
    }
    return i;
  },
  NamedType: e => e.name.value,
  ListType: e => "[" + _print(e.type) + "]",
  NonNullType: e => _print(e.type) + "!"
};

var _print = e => h[e.kind](e);

function print(e) {
  return m = "\n", h[e.kind] ? h[e.kind](e) : "";
}

var g = o((async function* _runPersisted(o) {
  var d = i(o.pluginConfig);
  var c = s(o);
  var u = c.createExternalFiles();
  if (u.length) {
    yield {
      kind: "EXTERNAL_WARNING"
    };
    await c.addVirtualFiles(u);
  }
  var f = c.build();
  var v = f.buildPluginInfo(o.pluginConfig);
  var m = f.getSourceFiles();
  yield {
    kind: "FILE_COUNT",
    fileCount: m.length
  };
  for (var h of m) {
    var g = h.fileName;
    var p = [];
    var S = [];
    var C = r(h, v);
    for (var A of C) {
      var k = f.getSourcePosition(h, A.node.getStart());
      g = k.fileName;
      if (!d.has(A.schema)) {
        S.push({
          message: A.schema ? `The '${A.schema}' schema is not in the configuration but was referenced by "graphql.persisted".` : d.size > 1 ? "The document is not for a known schema. Have you re-generated the output file?" : "Multiple schemas are configured, but the document is not for a specific schema.",
          file: k.fileName,
          line: k.line,
          col: k.col
        });
        continue;
      }
      var b = A.node.arguments[0];
      var y = A.node.arguments[1];
      var N = A.node.typeArguments && A.node.typeArguments[0];
      if (!b || !e.isStringLiteral(b)) {
        S.push({
          message: '"graphql.persisted" must be called with a string literal as the first argument.',
          file: k.fileName,
          line: k.line,
          col: k.col
        });
        continue;
      } else if (!y && !N) {
        S.push({
          message: '"graphql.persisted" is missing a document.\nThis may be passed as a generic such as `graphql.persisted<typeof document>` or as the second argument.',
          file: k.fileName,
          line: k.line,
          col: k.col
        });
        continue;
      }
      var V = null;
      var w = A.node;
      if (y && (e.isCallExpression(y) || e.isIdentifier(y))) {
        V = n(y, h.fileName, v).node;
        w = y;
      } else if (N && e.isTypeQueryNode(N)) {
        V = t(N, h.fileName, v).node;
        w = N;
      }
      if (!V) {
        S.push({
          message: `Could not find reference for "${w.getText()}".\nIf this is unexpected, please file an issue describing your case.`,
          file: k.fileName,
          line: k.line,
          col: k.col
        });
        continue;
      }
      if (!V || !e.isCallExpression(V) || !e.isNoSubstitutionTemplateLiteral(V.arguments[0]) && !e.isStringLiteral(V.arguments[0])) {
        S.push({
          message: `The referenced document of "${w.getText()}" contains no document string literal.\nIf this is unexpected, please file an issue describing your case.`,
          file: k.fileName,
          line: k.line,
          col: k.col
        });
        continue;
      }
      var D = [];
      var T = V.arguments[0].getText().slice(1, -1);
      if (V.arguments[1] && e.isArrayLiteralExpression(V.arguments[1])) {
        a(V.arguments[1], D, f.buildPluginInfo(o.pluginConfig));
      }
      var F = new Set;
      var x = void 0;
      if (o.disableNormalization) {
        x = T;
      } else {
        try {
          var E = parse(T);
          var I = new Set;
          for (var J of E.definitions) {
            if (J.kind === l && !I.has(J)) {
              stripUnmaskDirectivesFromDefinition(J);
            }
          }
          x = print(E);
        } catch (e) {
          S.push({
            message: `The referenced document of "${w.getText()}" could not be parsed.\nRun \`check\` to see specific validation errors.`,
            file: k.fileName,
            line: k.line,
            col: k.col
          });
          continue;
        }
      }
      for (var L of D) {
        stripUnmaskDirectivesFromDefinition(L);
        var O = print(L);
        if (!F.has(O)) {
          x += "\n\n" + print(L);
          F.add(O);
        }
      }
      p.push({
        schemaName: A.schema,
        hashKey: b.getText().slice(1, -1),
        document: x
      });
    }
    yield {
      kind: "FILE_PERSISTED",
      filePath: g,
      documents: p,
      warnings: S
    };
  }
}));

var stripUnmaskDirectivesFromDefinition = e => {
  e.directives = e.directives?.filter((e => "_unmask" !== e.name.value));
};

export { g as runPersisted };
//# sourceMappingURL=thread-chunk.mjs.map
