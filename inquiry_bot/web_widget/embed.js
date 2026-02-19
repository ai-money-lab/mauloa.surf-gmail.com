/**
 * ROCKEDGE 問い合わせBot — 埋め込みウィジェットスクリプト v2
 *
 * Intercom / Crisp / HubSpot のベストプラクティスを統合
 *
 * 使い方:
 *   <script src="https://your-domain.com/widget/embed.js"
 *           data-api="https://your-domain.com"
 *           data-position="bottom-right">
 *   </script>
 *
 * オプション:
 *   data-api       : Bot APIのベースURL（必須）
 *   data-position  : ウィジェットの位置 (bottom-right / bottom-left)
 *   data-color     : プライマリカラー (#1a1a2e)
 *   data-accent    : アクセントカラー (#e94560)
 *   data-greeting  : プロアクティブ挨拶テキスト
 *   data-delay     : 挨拶表示までの秒数 (デフォルト: 5)
 */
(function() {
  'use strict';

  // ═══ 設定取得 ═══
  var script = document.currentScript;
  var apiBase = script.getAttribute('data-api') || '';
  var position = script.getAttribute('data-position') || 'bottom-right';
  var primaryColor = script.getAttribute('data-color') || '#1a1a2e';
  var accentColor = script.getAttribute('data-accent') || '#e94560';
  var greetingText = script.getAttribute('data-greeting') || 'こんにちは！何かお手伝いできることはありますか？';
  var greetingDelay = parseInt(script.getAttribute('data-delay') || '5', 10) * 1000;

  var isOpen = false;
  var greetingShown = false;
  var greetingDismissed = false;
  var positionSide = position === 'bottom-left' ? 'left' : 'right';
  var oppositeSide = position === 'bottom-left' ? 'right' : 'left';

  // ═══ CSS注入 ═══
  var style = document.createElement('style');
  style.textContent = [
    /* ── Trigger button ── */
    '#rockedge-bot-trigger {',
    '  position: fixed;',
    '  ' + positionSide + ': 20px;',
    '  bottom: 20px;',
    '  width: 56px;',
    '  height: 56px;',
    '  border-radius: 16px;',
    '  background: linear-gradient(135deg, ' + accentColor + ', ' + primaryColor + ');',
    '  border: none;',
    '  cursor: pointer;',
    '  box-shadow: 0 4px 20px rgba(0,0,0,0.2);',
    '  z-index: 99999;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  transition: transform 250ms cubic-bezier(0.4,0,0.2,1), box-shadow 250ms cubic-bezier(0.4,0,0.2,1);',
    '  color: #fff;',
    '  padding: 0;',
    '  outline: none;',
    '}',
    '#rockedge-bot-trigger:hover {',
    '  transform: scale(1.08);',
    '  box-shadow: 0 6px 24px rgba(0,0,0,0.25);',
    '}',
    '#rockedge-bot-trigger:active { transform: scale(0.95); }',
    '#rockedge-bot-trigger:focus-visible {',
    '  outline: 2px solid ' + accentColor + ';',
    '  outline-offset: 3px;',
    '}',

    /* Trigger icon container */
    '#rockedge-bot-trigger .trigger-icon {',
    '  width: 24px;',
    '  height: 24px;',
    '  transition: transform 300ms cubic-bezier(0.4,0,0.2,1), opacity 200ms ease;',
    '  position: absolute;',
    '}',
    '#rockedge-bot-trigger .trigger-icon.chat-icon { opacity: 1; transform: scale(1) rotate(0); }',
    '#rockedge-bot-trigger .trigger-icon.close-icon { opacity: 0; transform: scale(0.5) rotate(-90deg); }',
    '#rockedge-bot-trigger.open .trigger-icon.chat-icon { opacity: 0; transform: scale(0.5) rotate(90deg); }',
    '#rockedge-bot-trigger.open .trigger-icon.close-icon { opacity: 1; transform: scale(1) rotate(0); }',

    /* Unread badge */
    '#rockedge-bot-badge {',
    '  position: absolute;',
    '  top: -4px;',
    '  ' + oppositeSide + ': -4px;',
    '  width: 18px;',
    '  height: 18px;',
    '  background: #ef4444;',
    '  border-radius: 50%;',
    '  border: 2px solid #fff;',
    '  font-size: 10px;',
    '  font-weight: 700;',
    '  color: #fff;',
    '  display: none;',
    '  align-items: center;',
    '  justify-content: center;',
    '  line-height: 1;',
    '  animation: rockedge-badge-in 400ms cubic-bezier(0.34, 1.56, 0.64, 1);',
    '}',
    '#rockedge-bot-badge.show { display: flex; }',

    '@keyframes rockedge-badge-in {',
    '  from { transform: scale(0); }',
    '  to { transform: scale(1); }',
    '}',

    /* ── Proactive greeting bubble ── */
    '#rockedge-greeting {',
    '  position: fixed;',
    '  ' + positionSide + ': 20px;',
    '  bottom: 88px;',
    '  max-width: 280px;',
    '  background: #fff;',
    '  border-radius: 16px 16px ' + (positionSide === 'right' ? '4px 16px' : '16px 4px') + ';',
    '  padding: 14px 18px;',
    '  box-shadow: 0 4px 24px rgba(0,0,0,0.12);',
    '  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", sans-serif;',
    '  font-size: 14px;',
    '  line-height: 1.5;',
    '  color: #1a1a2e;',
    '  z-index: 99998;',
    '  opacity: 0;',
    '  transform: translateY(10px) scale(0.95);',
    '  pointer-events: none;',
    '  transition: opacity 300ms cubic-bezier(0.4,0,0.2,1), transform 300ms cubic-bezier(0.4,0,0.2,1);',
    '  cursor: pointer;',
    '}',
    '#rockedge-greeting.show {',
    '  opacity: 1;',
    '  transform: translateY(0) scale(1);',
    '  pointer-events: auto;',
    '}',
    '#rockedge-greeting-close {',
    '  position: absolute;',
    '  top: 6px;',
    '  right: 8px;',
    '  width: 20px;',
    '  height: 20px;',
    '  border: none;',
    '  background: rgba(0,0,0,0.06);',
    '  border-radius: 50%;',
    '  cursor: pointer;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  font-size: 12px;',
    '  color: #9aa0a6;',
    '  padding: 0;',
    '  line-height: 1;',
    '  transition: background 150ms;',
    '}',
    '#rockedge-greeting-close:hover { background: rgba(0,0,0,0.12); }',

    /* ── Chat frame ── */
    '#rockedge-bot-frame {',
    '  position: fixed;',
    '  ' + positionSide + ': 20px;',
    '  bottom: 88px;',
    '  width: 400px;',
    '  height: 580px;',
    '  max-width: calc(100vw - 40px);',
    '  max-height: calc(100vh - 120px);',
    '  max-height: calc(100dvh - 120px);',
    '  border: none;',
    '  border-radius: 16px;',
    '  box-shadow: 0 8px 40px rgba(0,0,0,0.18);',
    '  z-index: 99998;',
    '  background: #fff;',
    '  opacity: 0;',
    '  transform: translateY(16px) scale(0.95);',
    '  transform-origin: bottom ' + positionSide + ';',
    '  pointer-events: none;',
    '  transition: opacity 300ms cubic-bezier(0.4,0,0.2,1), transform 300ms cubic-bezier(0.4,0,0.2,1);',
    '}',
    '#rockedge-bot-frame.open {',
    '  opacity: 1;',
    '  transform: translateY(0) scale(1);',
    '  pointer-events: auto;',
    '}',

    /* Mobile full-screen */
    '@media (max-width: 480px) {',
    '  #rockedge-bot-frame {',
    '    width: 100vw;',
    '    height: calc(100vh - 70px);',
    '    height: calc(100dvh - 70px);',
    '    ' + positionSide + ': 0;',
    '    bottom: 70px;',
    '    border-radius: 16px 16px 0 0;',
    '    max-width: 100vw;',
    '    max-height: calc(100vh - 70px);',
    '  }',
    '  #rockedge-bot-trigger {',
    '    ' + positionSide + ': 16px;',
    '    bottom: 16px;',
    '    width: 52px;',
    '    height: 52px;',
    '    border-radius: 14px;',
    '  }',
    '  #rockedge-greeting {',
    '    ' + positionSide + ': 16px;',
    '    bottom: 80px;',
    '    max-width: calc(100vw - 90px);',
    '  }',
    '}',

    /* Reduced motion */
    '@media (prefers-reduced-motion: reduce) {',
    '  #rockedge-bot-trigger,',
    '  #rockedge-bot-frame,',
    '  #rockedge-greeting,',
    '  #rockedge-bot-trigger .trigger-icon {',
    '    transition: none !important;',
    '  }',
    '}',

    /* Dark mode auto-detection for greeting */
    '@media (prefers-color-scheme: dark) {',
    '  #rockedge-greeting {',
    '    background: #2a2a3c;',
    '    color: #e0e0e6;',
    '    box-shadow: 0 4px 24px rgba(0,0,0,0.4);',
    '  }',
    '  #rockedge-greeting-close { color: #6c6c7e; background: rgba(255,255,255,0.08); }',
    '  #rockedge-greeting-close:hover { background: rgba(255,255,255,0.15); }',
    '}'
  ].join('\n');
  document.head.appendChild(style);

  // ═══ Trigger button ═══
  var trigger = document.createElement('button');
  trigger.id = 'rockedge-bot-trigger';
  trigger.setAttribute('aria-label', 'チャットを開く');
  trigger.innerHTML = [
    '<span class="trigger-icon chat-icon">',
    '  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">',
    '    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    '  </svg>',
    '</span>',
    '<span class="trigger-icon close-icon">',
    '  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">',
    '    <line x1="18" y1="6" x2="6" y2="18"/>',
    '    <line x1="6" y1="6" x2="18" y2="18"/>',
    '  </svg>',
    '</span>',
    '<span id="rockedge-bot-badge">1</span>'
  ].join('');

  // ═══ Proactive greeting bubble ═══
  var greeting = document.createElement('div');
  greeting.id = 'rockedge-greeting';
  greeting.innerHTML = greetingText + '<button id="rockedge-greeting-close" aria-label="閉じる">✕</button>';

  // ═══ iframeチャット ═══
  var frame = document.createElement('iframe');
  frame.id = 'rockedge-bot-frame';
  frame.src = apiBase + '/chat';
  frame.setAttribute('title', 'ROCKEDGE AIアシスタント');
  frame.setAttribute('loading', 'lazy');
  frame.setAttribute('allow', 'autoplay');

  // iframe内にAPI URLを渡す
  frame.onload = function() {
    try {
      frame.contentWindow.INQUIRY_BOT_API = apiBase;
    } catch(e) {
      // クロスオリジンの場合はpostMessageで対応
      frame.contentWindow.postMessage({ type: 'rockedge-config', apiBase: apiBase }, '*');
    }
  };

  // ═══ イベントハンドラ ═══
  function toggleWidget() {
    isOpen = !isOpen;

    if (isOpen) {
      frame.classList.add('open');
      trigger.classList.add('open');
      trigger.setAttribute('aria-label', 'チャットを閉じる');
      dismissGreeting();
      hideBadge();
    } else {
      frame.classList.remove('open');
      trigger.classList.remove('open');
      trigger.setAttribute('aria-label', 'チャットを開く');
    }
  }

  function dismissGreeting() {
    greetingDismissed = true;
    greeting.classList.remove('show');
  }

  function hideBadge() {
    var badge = document.getElementById('rockedge-bot-badge');
    if (badge) badge.classList.remove('show');
  }

  function showGreeting() {
    if (greetingDismissed || isOpen || greetingShown) return;
    greetingShown = true;
    greeting.classList.add('show');
    var badge = document.getElementById('rockedge-bot-badge');
    if (badge) badge.classList.add('show');
  }

  trigger.addEventListener('click', toggleWidget);

  greeting.addEventListener('click', function(e) {
    if (e.target.id === 'rockedge-greeting-close') {
      e.stopPropagation();
      dismissGreeting();
      return;
    }
    dismissGreeting();
    if (!isOpen) toggleWidget();
  });

  // ESCキーでウィジェットを閉じる
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && isOpen) {
      toggleWidget();
    }
  });

  // iframe からの close メッセージを受信
  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'rockedge-close' && isOpen) {
      toggleWidget();
    }
  });

  // ═══ DOM追加 ═══
  document.body.appendChild(greeting);
  document.body.appendChild(trigger);
  document.body.appendChild(frame);

  // ═══ プロアクティブ挨拶（一定秒後） ═══
  setTimeout(showGreeting, greetingDelay);
})();
