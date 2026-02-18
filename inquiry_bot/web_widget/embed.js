/**
 * ROCKEDGE 問い合わせBot — 埋め込みウィジェットスクリプト
 *
 * 使い方:
 *   <script src="https://your-domain.com/widget/embed.js"
 *           data-api="https://your-domain.com"
 *           data-position="bottom-right">
 *   </script>
 *
 * オプション:
 *   data-api      : Bot APIのベースURL（必須）
 *   data-position : ウィジェットの位置 (bottom-right / bottom-left)
 *   data-color    : プライマリカラー (#1a1a2e)
 *   data-accent   : アクセントカラー (#e94560)
 */
(function() {
  'use strict';

  // 設定取得
  var script = document.currentScript;
  var apiBase = script.getAttribute('data-api') || '';
  var position = script.getAttribute('data-position') || 'bottom-right';
  var primaryColor = script.getAttribute('data-color') || '#1a1a2e';
  var accentColor = script.getAttribute('data-accent') || '#e94560';

  var sessionId = null;
  var isOpen = false;

  // CSS注入
  var style = document.createElement('style');
  style.textContent = '\
    #rockedge-bot-trigger {\
      position: fixed;\
      ' + (position === 'bottom-left' ? 'left' : 'right') + ': 20px;\
      bottom: 20px;\
      width: 60px;\
      height: 60px;\
      border-radius: 50%;\
      background: linear-gradient(135deg, ' + accentColor + ', ' + primaryColor + ');\
      border: none;\
      cursor: pointer;\
      box-shadow: 0 4px 16px rgba(0,0,0,0.2);\
      z-index: 99999;\
      display: flex;\
      align-items: center;\
      justify-content: center;\
      transition: transform 0.2s;\
      font-size: 24px;\
      color: #fff;\
    }\
    #rockedge-bot-trigger:hover { transform: scale(1.1); }\
    #rockedge-bot-frame {\
      position: fixed;\
      ' + (position === 'bottom-left' ? 'left' : 'right') + ': 20px;\
      bottom: 90px;\
      width: 380px;\
      height: 560px;\
      max-width: calc(100vw - 40px);\
      max-height: calc(100vh - 120px);\
      border: none;\
      border-radius: 16px;\
      box-shadow: 0 8px 32px rgba(0,0,0,0.15);\
      z-index: 99998;\
      display: none;\
      background: #fff;\
    }\
    #rockedge-bot-frame.open { display: block; }\
    @media (max-width: 480px) {\
      #rockedge-bot-frame {\
        width: calc(100vw - 20px);\
        height: calc(100vh - 100px);\
        ' + (position === 'bottom-left' ? 'left' : 'right') + ': 10px;\
        bottom: 80px;\
        border-radius: 12px;\
      }\
    }\
  ';
  document.head.appendChild(style);

  // トリガーボタン
  var trigger = document.createElement('button');
  trigger.id = 'rockedge-bot-trigger';
  trigger.innerHTML = '&#128172;';
  trigger.setAttribute('aria-label', 'チャットを開く');
  trigger.onclick = function() {
    isOpen = !isOpen;
    frame.className = isOpen ? 'open' : '';
    trigger.innerHTML = isOpen ? '&#10005;' : '&#128172;';
  };

  // iframeチャット
  var frame = document.createElement('iframe');
  frame.id = 'rockedge-bot-frame';
  frame.src = apiBase + '/chat';
  frame.setAttribute('title', 'ROCKEDGE AIアシスタント');

  // iframe内にAPI URLを渡す
  frame.onload = function() {
    try {
      frame.contentWindow.INQUIRY_BOT_API = apiBase;
    } catch(e) {
      // クロスオリジンの場合はpostMessageで対応
    }
  };

  // DOM追加
  document.body.appendChild(trigger);
  document.body.appendChild(frame);
})();
