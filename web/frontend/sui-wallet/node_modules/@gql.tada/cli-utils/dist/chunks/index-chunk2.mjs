import { isMainThread as e, parentPort as r, Worker as n, SHARE_ENV as t } from "node:worker_threads";

var a = r;

if (!e && !a) {
  throw new ReferenceError("Failed to receive parent message port");
}

var i = function(e) {
  e.Start = "START";
  e.Close = "CLOSE";
  e.Pull = "PULL";
  return e;
}(i || {});

var s = function(e) {
  e.Next = "NEXT";
  e.Throw = "THROW";
  e.Return = "RETURN";
  return e;
}(s || {});

var o = {
  env: t,
  stderr: !1,
  stdout: !1,
  stdin: !1
};

var getMessageData = e => {
  var r = e.data;
  if (e.kind === s.Throw) {
    return "object" == typeof r && r && null != e.extra ? Object.assign(r, e.extra) : r;
  } else {
    return r;
  }
};

var asyncIteratorSymbol = () => "function" == typeof Symbol && Symbol.asyncIterator || "@@asyncIterator";

function expose(r) {
  if (e) {
    var t = function captureStack() {
      var e = new Error;
      var r = Error.prepareStackTrace;
      try {
        var n;
        Error.prepareStackTrace = (e, r) => n = r;
        Error.captureStackTrace(e);
        if (!e.stack) {
          throw e;
        }
        return n && n.slice(2) || [];
      } finally {
        Error.prepareStackTrace = r;
      }
    }()[0];
    var u = t && t.getFileName();
    if (!u) {
      throw new ReferenceError("Captured stack trace is empty");
    }
    return function main(e) {
      var r;
      var t = 0;
      var a = 0;
      return (...u) => {
        if (!r) {
          (r = new n(e, o)).unref();
        }
        var c = r;
        var d = 0 | ++a;
        var l = [];
        var f = !1;
        var v = !1;
        var p = !1;
        var g;
        var k;
        function cleanup() {
          if (v) {
            return;
          }
          v = !0;
          g = void 0;
          k = void 0;
          c.removeListener("message", receiveMessage);
          c.removeListener("error", receiveError);
          c.removeListener("exit", receiveExit);
          if (0 == --t) {
            c.unref();
          }
        }
        function sendMessage(e) {
          c.postMessage({
            id: d,
            kind: e
          });
        }
        function fail(e) {
          var r = k;
          cleanup();
          if (r) {
            r(e);
          } else {
            l.length = 1;
            l[0] = {
              id: d,
              kind: s.Throw,
              data: e
            };
          }
        }
        function receiveError(e) {
          fail(e);
        }
        function receiveExit(e) {
          if (v) {
            return;
          }
          if (r === c) {
            r = void 0;
          }
          fail(new Error(`Worker stopped unexpectedly with exit code ${e}`));
        }
        function receiveMessage(e) {
          var r = e && "object" == typeof e && "kind" in e ? e : null;
          if (!r) {
            return;
          } else if (k && r.kind === s.Throw) {
            k(getMessageData(r));
            cleanup();
          } else if (g && r.kind === s.Return) {
            g({
              done: !0,
              value: getMessageData(r)
            });
            cleanup();
          } else if (g && r.kind === s.Next) {
            p = !1;
            g({
              done: !1,
              value: getMessageData(r)
            });
          } else if (r.kind === s.Throw || r.kind === s.Return) {
            l.push(r);
            cleanup();
          } else if (r.kind === s.Next) {
            l.push(r);
            p = !1;
          }
        }
        return {
          async next() {
            if (!f) {
              f = !0;
              if (0 == t++) {
                c.ref();
              }
              c.addListener("message", receiveMessage);
              c.addListener("error", receiveError);
              c.addListener("exit", receiveExit);
              c.postMessage({
                id: d,
                kind: i.Start,
                data: u
              });
            }
            if (v && !l.length) {
              return {
                done: !0
              };
            } else if (!v && !p && l.length <= 1) {
              p = !0;
              sendMessage(i.Pull);
            }
            var e = l.shift();
            if (e && e.kind === s.Throw) {
              cleanup();
              throw getMessageData(e);
            } else if (e && e.kind === s.Return) {
              cleanup();
              return {
                value: getMessageData(e),
                done: !0
              };
            } else if (e && e.kind === s.Next) {
              return {
                value: getMessageData(e),
                done: !1
              };
            } else {
              return new Promise(((e, r) => {
                g = r => {
                  g = void 0;
                  k = void 0;
                  e(r);
                };
                k = e => {
                  g = void 0;
                  k = void 0;
                  r(e);
                };
              }));
            }
          },
          async return() {
            if (!v) {
              cleanup();
              sendMessage(i.Close);
            }
            return {
              done: !0
            };
          },
          [asyncIteratorSymbol()]() {
            return this;
          }
        };
      };
    }(u.startsWith("file://") ? new URL(u) : u);
  } else {
    a.addListener("message", (e => {
      var n = e && "object" == typeof e && "kind" in e ? e : null;
      if (n) {
        !function thread(e, r) {
          if (e.kind !== i.Start) {
            return;
          }
          var n = e.id;
          var t = r(...e.data);
          var o = !1;
          var u = !1;
          var c = !1;
          function cleanup() {
            o = !0;
            a.removeListener("message", receiveMessage);
          }
          async function sendMessage(e, r) {
            try {
              var i = {
                id: n,
                kind: e,
                data: r
              };
              if (e === s.Throw && "object" == typeof r && null != r) {
                i.extra = {
                  ...r
                };
              }
              a.postMessage(i);
            } catch (e) {
              cleanup();
              if (t.throw) {
                var o = await t.throw();
                if (!1 === o.done && t.return) {
                  o = await t.return();
                  sendMessage(s.Return, o.value);
                } else {
                  sendMessage(s.Return, o.value);
                }
              } else {
                sendMessage(s.Return);
              }
            }
          }
          async function receiveMessage(e) {
            var r = e && "object" == typeof e && "kind" in e ? e : null;
            var n;
            if (!r) {
              return;
            } else if (r.kind === i.Close) {
              cleanup();
              if (t.return) {
                t.return();
              }
            } else if (r.kind === i.Pull && c) {
              u = !0;
            } else if (r.kind === i.Pull) {
              for (u = c = !0; u && !o; ) {
                try {
                  if ((n = await t.next()).done) {
                    cleanup();
                    if (t.return) {
                      n = await t.return();
                    }
                    sendMessage(s.Return, n.value);
                  } else {
                    u = !1;
                    sendMessage(s.Next, n.value);
                  }
                } catch (e) {
                  cleanup();
                  sendMessage(s.Throw, e);
                }
              }
              c = !1;
            }
          }
          a.addListener("message", receiveMessage);
        }(n, r);
      }
    }));
    return r;
  }
}

export { expose as e };
//# sourceMappingURL=index-chunk2.mjs.map
