var e = require("node:worker_threads");

var r = e.parentPort;

if (!e.isMainThread && !r) {
  throw new ReferenceError("Failed to receive parent message port");
}

var n = function(e) {
  e.Start = "START";
  e.Close = "CLOSE";
  e.Pull = "PULL";
  return e;
}(n || {});

var a = function(e) {
  e.Next = "NEXT";
  e.Throw = "THROW";
  e.Return = "RETURN";
  return e;
}(a || {});

var t = {
  env: e.SHARE_ENV,
  stderr: !1,
  stdout: !1,
  stdin: !1
};

var getMessageData = e => {
  var r = e.data;
  if (e.kind === a.Throw) {
    return "object" == typeof r && r && null != e.extra ? Object.assign(r, e.extra) : r;
  } else {
    return r;
  }
};

var asyncIteratorSymbol = () => "function" == typeof Symbol && Symbol.asyncIterator || "@@asyncIterator";

exports.expose = function expose(i) {
  if (e.isMainThread) {
    var s = function captureStack() {
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
    var o = s && s.getFileName();
    if (!o) {
      throw new ReferenceError("Captured stack trace is empty");
    }
    return function main(r) {
      var i;
      var s = 0;
      var o = 0;
      return (...u) => {
        if (!i) {
          (i = new e.Worker(r, t)).unref();
        }
        var d = i;
        var c = 0 | ++o;
        var l = [];
        var f = !1;
        var v = !1;
        var p = !1;
        var k;
        var g;
        function cleanup() {
          if (v) {
            return;
          }
          v = !0;
          k = void 0;
          g = void 0;
          d.removeListener("message", receiveMessage);
          d.removeListener("error", receiveError);
          d.removeListener("exit", receiveExit);
          if (0 == --s) {
            d.unref();
          }
        }
        function sendMessage(e) {
          d.postMessage({
            id: c,
            kind: e
          });
        }
        function fail(e) {
          var r = g;
          cleanup();
          if (r) {
            r(e);
          } else {
            l.length = 1;
            l[0] = {
              id: c,
              kind: a.Throw,
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
          if (i === d) {
            i = void 0;
          }
          fail(new Error(`Worker stopped unexpectedly with exit code ${e}`));
        }
        function receiveMessage(e) {
          var r = e && "object" == typeof e && "kind" in e ? e : null;
          if (!r) {
            return;
          } else if (g && r.kind === a.Throw) {
            g(getMessageData(r));
            cleanup();
          } else if (k && r.kind === a.Return) {
            k({
              done: !0,
              value: getMessageData(r)
            });
            cleanup();
          } else if (k && r.kind === a.Next) {
            p = !1;
            k({
              done: !1,
              value: getMessageData(r)
            });
          } else if (r.kind === a.Throw || r.kind === a.Return) {
            l.push(r);
            cleanup();
          } else if (r.kind === a.Next) {
            l.push(r);
            p = !1;
          }
        }
        return {
          async next() {
            if (!f) {
              f = !0;
              if (0 == s++) {
                d.ref();
              }
              d.addListener("message", receiveMessage);
              d.addListener("error", receiveError);
              d.addListener("exit", receiveExit);
              d.postMessage({
                id: c,
                kind: n.Start,
                data: u
              });
            }
            if (v && !l.length) {
              return {
                done: !0
              };
            } else if (!v && !p && l.length <= 1) {
              p = !0;
              sendMessage(n.Pull);
            }
            var e = l.shift();
            if (e && e.kind === a.Throw) {
              cleanup();
              throw getMessageData(e);
            } else if (e && e.kind === a.Return) {
              cleanup();
              return {
                value: getMessageData(e),
                done: !0
              };
            } else if (e && e.kind === a.Next) {
              return {
                value: getMessageData(e),
                done: !1
              };
            } else {
              return new Promise(((e, r) => {
                k = r => {
                  k = void 0;
                  g = void 0;
                  e(r);
                };
                g = e => {
                  k = void 0;
                  g = void 0;
                  r(e);
                };
              }));
            }
          },
          async return() {
            if (!v) {
              cleanup();
              sendMessage(n.Close);
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
    }(o.startsWith("file://") ? new URL(o) : o);
  } else {
    r.addListener("message", (e => {
      var t = e && "object" == typeof e && "kind" in e ? e : null;
      if (t) {
        !function thread(e, t) {
          if (e.kind !== n.Start) {
            return;
          }
          var i = e.id;
          var s = t(...e.data);
          var o = !1;
          var u = !1;
          var d = !1;
          function cleanup() {
            o = !0;
            r.removeListener("message", receiveMessage);
          }
          async function sendMessage(e, n) {
            try {
              var t = {
                id: i,
                kind: e,
                data: n
              };
              if (e === a.Throw && "object" == typeof n && null != n) {
                t.extra = {
                  ...n
                };
              }
              r.postMessage(t);
            } catch (e) {
              cleanup();
              if (s.throw) {
                var o = await s.throw();
                if (!1 === o.done && s.return) {
                  o = await s.return();
                  sendMessage(a.Return, o.value);
                } else {
                  sendMessage(a.Return, o.value);
                }
              } else {
                sendMessage(a.Return);
              }
            }
          }
          async function receiveMessage(e) {
            var r = e && "object" == typeof e && "kind" in e ? e : null;
            var t;
            if (!r) {
              return;
            } else if (r.kind === n.Close) {
              cleanup();
              if (s.return) {
                s.return();
              }
            } else if (r.kind === n.Pull && d) {
              u = !0;
            } else if (r.kind === n.Pull) {
              for (u = d = !0; u && !o; ) {
                try {
                  if ((t = await s.next()).done) {
                    cleanup();
                    if (s.return) {
                      t = await s.return();
                    }
                    sendMessage(a.Return, t.value);
                  } else {
                    u = !1;
                    sendMessage(a.Next, t.value);
                  }
                } catch (e) {
                  cleanup();
                  sendMessage(a.Throw, e);
                }
              }
              d = !1;
            }
          }
          r.addListener("message", receiveMessage);
        }(t, i);
      }
    }));
    return i;
  }
};
//# sourceMappingURL=index-chunk2.js.map
