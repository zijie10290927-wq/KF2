/**
 * AIChatWidget — 嵌入式 AI 智能客服 JS SDK
 * 版本: v1.0.0
 * 全局 API: window.AIChatWidget
 *
 * 用法：
 *   <script src="https://your-domain/api/v1/widget/embed.js"></script>
 *   <script>
 *     AIChatWidget.init({
 *       appKey: 'YOUR_APP_KEY',
 *       position: 'bottom-right',
 *       welcomeMessage: '您好！我是AI智能客服，请问有什么可以帮您？'
 *     });
 *   </script>
 *
 * 全局方法：init / open / close / sendMessage / getState / setConfig / destroy
 */
(function (global, factory) {
  'use strict';
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    global.AIChatWidget = factory();
  }
}(typeof window !== 'undefined' ? window : this, function () {
  'use strict';

  // ===================== 默认配置 ===================== //
  var DEFAULTS = {
    appKey: '',                              // 必填
    apiBase: '',                             // 自动推断（embed.js 地址）
    position: 'bottom-right',                // bottom-right | bottom-left
    zIndex: 99999,
    theme: {
      primaryColor: '#409EFF',
      backgroundColor: '#FFFFFF',
      textColor: '#303133',
      borderRadius: '12px',
      headerHeight: '56px'
    },
    bubbleText: 'AI 客服',
    welcomeMessage: '您好！我是AI智能客服，有什么可以帮您？',
    maxWidth: '400px',
    maxHeight: '600px',
    autoOpen: false,
    autoOpenDelay: 3000,
    placeholder: '请输入您的问题...',
    sendButtonText: '发送',
    showBubble: true,
    // 生命周期回调
    onOpen: null,
    onClose: null,
    onMessage: null,
    onError: null
  };

  // ===================== 状态 ===================== //
  var state = {
    initialized: false,
    opened: false,
    sessionId: null,
    messages: [],                            // [{role, content, sources, fallback, ts}]
    streaming: false,
    abortController: null,
    config: null
  };

  // ===================== 工具函数 ===================== //
  function deepMerge(target, source) {
    var out = {};
    for (var k in target) {
      if (Object.prototype.hasOwnProperty.call(target, k)) {
        if (typeof target[k] === 'object' && target[k] !== null && !Array.isArray(target[k])) {
          out[k] = deepMerge(target[k] || {}, source[k] || {});
        } else {
          out[k] = source[k] !== undefined ? source[k] : target[k];
        }
      }
    }
    for (var j in source) {
      if (!Object.prototype.hasOwnProperty.call(out, j)) out[j] = source[j];
    }
    return out;
  }

  function qs(str) {
    return encodeURIComponent(str);
  }

  function inferApiBase() {
    if (state.config.apiBase) return state.config.apiBase.replace(/\/$/, '');
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      var src = scripts[i].src || '';
      if (src.indexOf('/widget/embed.js') > -1) {
        return src.split('/widget/embed.js')[0];
      }
    }
    return '';
  }

  function applyStyles(el, styles) {
    for (var k in styles) {
      if (Object.prototype.hasOwnProperty.call(styles, k)) {
        el.style[k] = styles[k];
      }
    }
  }

  // ===================== DOM 构建 ===================== //
  var dom = {
    styleNode: null,
    bubble: null,
    window: null,
    header: null,
    titleEl: null,
    closeBtn: null,
    msgBox: null,
    input: null,
    sendBtn: null
  };

  function injectStyles() {
    if (dom.styleNode) return;
    var cfg = state.config;
    var css = '' +
      '.aichat-bubble{' +
        'position:fixed;' + (cfg.position === 'bottom-left' ? 'left:24px;' : 'right:24px;') +
        'bottom:24px;width:56px;height:56px;border-radius:50%;' +
        'background:' + cfg.theme.primaryColor + ';' +
        'color:#fff;display:flex;align-items:center;justify-content:center;' +
        'cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,0.2);z-index:' + cfg.zIndex + ';' +
        'font-size:24px;transition:transform 0.2s;' +
      '}' +
      '.aichat-bubble:hover{transform:scale(1.05);}' +
      '.aichat-window{' +
        'position:fixed;' + (cfg.position === 'bottom-left' ? 'left:24px;' : 'right:24px;') +
        'bottom:24px;width:' + cfg.maxWidth + ';max-width:calc(100vw - 48px);' +
        'height:' + cfg.maxHeight + ';max-height:calc(100vh - 48px);' +
        'background:' + cfg.theme.backgroundColor + ';' +
        'color:' + cfg.theme.textColor + ';' +
        'border-radius:' + cfg.theme.borderRadius + ';' +
        'box-shadow:0 8px 32px rgba(0,0,0,0.18);display:flex;flex-direction:column;' +
        'overflow:hidden;z-index:' + cfg.zIndex + ';' +
        'transform:scale(0.95);opacity:0;pointer-events:none;' +
        'transition:transform 0.2s, opacity 0.2s;' +
      '}' +
      '.aichat-window.open{transform:scale(1);opacity:1;pointer-events:auto;}' +
      '.aichat-header{' +
        'background:' + cfg.theme.primaryColor + ';color:#fff;' +
        'padding:14px 18px;font-size:15px;font-weight:500;display:flex;' +
        'align-items:center;justify-content:space-between;height:' + cfg.theme.headerHeight + ';' +
      '}' +
      '.aichat-close{cursor:pointer;font-size:22px;line-height:1;opacity:0.85;}' +
      '.aichat-close:hover{opacity:1;}' +
      '.aichat-messages{flex:1;overflow-y:auto;padding:16px;background:#f5f7fa;}' +
      '.aichat-msg{margin-bottom:12px;max-width:80%;padding:10px 14px;' +
        'border-radius:' + cfg.theme.borderRadius + ';word-wrap:break-word;' +
        'white-space:pre-wrap;line-height:1.5;font-size:14px;' +
      '}' +
      '.aichat-msg.user{background:' + cfg.theme.primaryColor + ';color:#fff;margin-left:auto;}' +
      '.aichat-msg.bot{background:#fff;color:' + cfg.theme.textColor + ';border:1px solid #e4e7ed;}' +
      '.aichat-sources{margin-top:8px;font-size:12px;color:#909399;}' +
      '.aichat-input{display:flex;padding:12px;border-top:1px solid #e4e7ed;background:#fff;}' +
      '.aichat-input input{flex:1;padding:10px 14px;border:1px solid #dcdfe6;' +
        'border-radius:8px;outline:none;font-size:14px;' +
      '}' +
      '.aichat-input button{margin-left:8px;padding:0 18px;background:' + cfg.theme.primaryColor + ';' +
        'color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;' +
      '}' +
      '.aichat-typing{display:inline-block;width:8px;height:14px;background:#909399;' +
        'margin-left:2px;animation:aichat-blink 1s infinite;' +
      '}' +
      '@keyframes aichat-blink{0%,100%{opacity:0;}50%{opacity:1;}}' +
      '@media (max-width:480px){' +
        '.aichat-window{width:100%!important;height:100%!important;' +
        'left:0!important;right:0!important;bottom:0!important;top:0!important;' +
        'border-radius:0!important;}' +
        '.aichat-bubble{bottom:16px;' + (cfg.position === 'bottom-left' ? 'left:16px;' : 'right:16px;') + '}' +
      '}';
    dom.styleNode = document.createElement('style');
    dom.styleNode.setAttribute('data-aichat', 'true');
    dom.styleNode.innerHTML = css;
    document.head.appendChild(dom.styleNode);
  }

  function buildDom() {
    var cfg = state.config;

    // 气泡
    if (cfg.showBubble) {
      dom.bubble = document.createElement('div');
      dom.bubble.className = 'aichat-bubble';
      dom.bubble.innerHTML = '<span>💬</span>';
      dom.bubble.title = cfg.bubbleText;
      dom.bubble.addEventListener('click', open);
      document.body.appendChild(dom.bubble);
    }

    // 聊天窗口
    dom.window = document.createElement('div');
    dom.window.className = 'aichat-window';

    // 头部
    dom.header = document.createElement('div');
    dom.header.className = 'aichat-header';
    dom.titleEl = document.createElement('span');
    dom.titleEl.textContent = cfg.bubbleText;
    dom.closeBtn = document.createElement('span');
    dom.closeBtn.className = 'aichat-close';
    dom.closeBtn.innerHTML = '&times;';
    dom.closeBtn.addEventListener('click', close);
    dom.header.appendChild(dom.titleEl);
    dom.header.appendChild(dom.closeBtn);

    // 消息区
    dom.msgBox = document.createElement('div');
    dom.msgBox.className = 'aichat-messages';

    // 输入区
    var inputWrap = document.createElement('div');
    inputWrap.className = 'aichat-input';
    dom.input = document.createElement('input');
    dom.input.type = 'text';
    dom.input.placeholder = cfg.placeholder;
    dom.input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.keyCode === 13) {
        e.preventDefault();
        _sendFromInput();
      }
    });
    dom.sendBtn = document.createElement('button');
    dom.sendBtn.textContent = cfg.sendButtonText;
    dom.sendBtn.addEventListener('click', _sendFromInput);
    inputWrap.appendChild(dom.input);
    inputWrap.appendChild(dom.sendBtn);

    dom.window.appendChild(dom.header);
    dom.window.appendChild(dom.msgBox);
    dom.window.appendChild(inputWrap);
    document.body.appendChild(dom.window);
  }

  // ===================== 消息渲染 ===================== //
  function appendMessage(role, content, sources) {
    var msg = { role: role, content: content, sources: sources || null, ts: Date.now() };
    state.messages.push(msg);

    var el = document.createElement('div');
    el.className = 'aichat-msg ' + role;
    el.textContent = content;

    if (sources && sources.length) {
      var srcEl = document.createElement('div');
      srcEl.className = 'aichat-sources';
      srcEl.textContent = '📎 参考来源：' + sources.map(function (s) {
        return s.title;
      }).join('、');
      el.appendChild(srcEl);
    }

    dom.msgBox.appendChild(el);
    _scrollToBottom();
    return el;
  }

  function appendTyping() {
    var el = document.createElement('div');
    el.className = 'aichat-msg bot';
    var cursor = document.createElement('span');
    cursor.className = 'aichat-typing';
    el.appendChild(cursor);
    dom.msgBox.appendChild(el);
    _scrollToBottom();
    return el;
  }

  function _scrollToBottom() {
    dom.msgBox.scrollTop = dom.msgBox.scrollHeight;
  }

  // ===================== SSE 流式请求 ===================== //
  async function streamMessage(text) {
    var cfg = state.config;
    var apiBase = inferApiBase();

    // 确保会话存在
    if (!state.sessionId) {
      try {
        var sessionRes = await fetch(apiBase + '/api/v1/widget/session', {
          method: 'POST',
          headers: { 'X-Widget-App-Key': cfg.appKey }
        });
        var sessionData = await sessionRes.json();
        if (sessionData.code === 0 && sessionData.data) {
          state.sessionId = sessionData.data.session_id;
        }
      } catch (e) {
        if (cfg.onError) cfg.onError(e);
        appendMessage('bot', '创建会话失败：' + e.message);
        return;
      }
    }

    state.streaming = true;
    if (state.abortController) state.abortController.abort();
    state.abortController = (typeof AbortController !== 'undefined') ? new AbortController() : null;

    var typingEl = appendTyping();
    var botEl = null;
    var botContent = '';
    var sources = [];

    try {
      var resp = await fetch(apiBase + '/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId,
          message: text,
          history: state.messages.slice(-10).map(function (m) {
            return { role: m.role, content: m.content };
          })
        }),
        signal: state.abortController ? state.abortController.signal : undefined
      });

      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      var reader = resp.body.getReader();
      var decoder = new TextDecoder('utf-8');
      var buffer = '';

      while (true) {
        var chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });

        var lines = buffer.split('\n');
        buffer = lines.pop();

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i];
          if (line.indexOf('event: ') === 0) {
            // 读取下一行 data
            var nextLine = lines[i + 1] || '';
            if (nextLine.indexOf('data: ') === 0) {
              var evtType = line.slice(7);
              var dataStr = nextLine.slice(6);
              try {
                var data = JSON.parse(dataStr);
                _handleSSEEvent(evtType, data, function (content) {
                  botContent += content;
                  if (!botEl) {
                    if (typingEl && typingEl.parentNode) {
                      typingEl.parentNode.removeChild(typingEl);
                      typingEl = null;
                    }
                    botEl = appendMessage('bot', botContent);
                  } else {
                    botEl.firstChild ? (botEl.firstChild.textContent = botContent) : (botEl.textContent = botContent);
                    _scrollToBottom();
                  }
                }, function (srcs) {
                  sources = srcs;
                });
              } catch (e) {
                // 解析失败忽略
              }
            }
          }
        }
      }

      // 清理 typing 指示器
      if (typingEl && typingEl.parentNode) {
        typingEl.parentNode.removeChild(typingEl);
      }
      // 渲染最终消息
      if (!botEl && botContent) {
        botEl = appendMessage('bot', botContent, sources);
      } else if (botEl && sources.length) {
        var srcEl = document.createElement('div');
        srcEl.className = 'aichat-sources';
        srcEl.textContent = '📎 参考来源：' + sources.map(function (s) { return s.title; }).join('、');
        botEl.appendChild(srcEl);
      }

      if (cfg.onMessage) cfg.onMessage({ role: 'bot', content: botContent, sources: sources });
    } catch (e) {
      if (typingEl && typingEl.parentNode) typingEl.parentNode.removeChild(typingEl);
      if (e.name !== 'AbortError') {
        appendMessage('bot', '请求失败：' + e.message);
        if (cfg.onError) cfg.onError(e);
      }
    } finally {
      state.streaming = false;
      state.abortController = null;
    }
  }

  function _handleSSEEvent(evtType, data, onAnswer, onSource) {
    if (evtType === 'answer' && data.content) {
      onAnswer(data.content);
    } else if (evtType === 'source' && Array.isArray(data.sources)) {
      onSource(data.sources);
    } else if (evtType === 'fallback') {
      // 兜底话术：拼接为文本
      var fbText = '';
      if (data.show_transfer) fbText += '\n如需进一步帮助，请输入「转人工」';
      if (data.show_phone) fbText += '\n或拨打客服电话：' + (data.phone || '');
      if (fbText) onAnswer(fbText);
    }
    // done / error 不在此处理
  }

  function _sendFromInput() {
    var text = dom.input.value.trim();
    if (!text || state.streaming) return;
    dom.input.value = '';
    appendMessage('user', text);
    streamMessage(text);
  }

  // ===================== 公共 API ===================== //
  function open() {
    if (state.opened) return;
    if (!dom.window) return;
    dom.window.classList.add('open');
    if (dom.bubble) dom.bubble.style.display = 'none';
    state.opened = true;
    if (state.config.onOpen) state.config.onOpen();
    dom.input.focus();
  }

  function close() {
    if (!state.opened) return;
    if (!dom.window) return;
    dom.window.classList.remove('open');
    if (dom.bubble) dom.bubble.style.display = 'flex';
    state.opened = false;
    if (state.config.onClose) state.config.onClose();
  }

  function sendMessage(text) {
    if (!state.initialized) return;
    if (!text || state.streaming) return;
    appendMessage('user', text);
    streamMessage(text);
  }

  function getState() {
    return {
      initialized: state.initialized,
      opened: state.opened,
      sessionId: state.sessionId,
      streaming: state.streaming,
      messages: state.messages.slice()
    };
  }

  function setConfig(key, value) {
    if (!state.initialized) return;
    if (key === 'theme') {
      state.config.theme = deepMerge(state.config.theme, value || {});
      // 重新注入样式
      if (dom.styleNode) dom.styleNode.parentNode.removeChild(dom.styleNode);
      dom.styleNode = null;
      injectStyles();
    } else {
      state.config[key] = value;
      if (key === 'bubbleText' && dom.titleEl) dom.titleEl.textContent = value;
      if (key === 'placeholder' && dom.input) dom.input.placeholder = value;
      if (key === 'sendButtonText' && dom.sendBtn) dom.sendBtn.textContent = value;
    }
  }

  function destroy() {
    if (state.abortController) state.abortController.abort();
    if (dom.bubble && dom.bubble.parentNode) dom.bubble.parentNode.removeChild(dom.bubble);
    if (dom.window && dom.window.parentNode) dom.window.parentNode.removeChild(dom.window);
    if (dom.styleNode && dom.styleNode.parentNode) dom.styleNode.parentNode.removeChild(dom.styleNode);
    dom = { styleNode: null, bubble: null, window: null, header: null, titleEl: null, closeBtn: null, msgBox: null, input: null, sendBtn: null };
    state = {
      initialized: false, opened: false, sessionId: null, messages: [],
      streaming: false, abortController: null, config: null
    };
  }

  function init(userConfig) {
    if (state.initialized) {
      console.warn('[AIChatWidget] already initialized');
      return;
    }
    if (!userConfig || !userConfig.appKey) {
      console.error('[AIChatWidget] appKey is required');
      return;
    }
    state.config = deepMerge(DEFAULTS, userConfig);

    // 等待 DOM ready
    function _start() {
      injectStyles();
      buildDom();

      // 欢迎消息
      if (state.config.welcomeMessage) {
        appendMessage('bot', state.config.welcomeMessage);
      }

      // 自动打开
      if (state.config.autoOpen) {
        setTimeout(open, state.config.autoOpenDelay || 3000);
      }

      state.initialized = true;
    }

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', _start);
    } else {
      _start();
    }
  }

  return {
    init: init,
    open: open,
    close: close,
    sendMessage: sendMessage,
    getState: getState,
    setConfig: setConfig,
    destroy: destroy,
    version: '1.0.0'
  };
}));
