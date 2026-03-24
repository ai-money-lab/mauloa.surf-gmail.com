//+------------------------------------------------------------------+
//|                    SUNRISE EA v7.25 BALANCED                     |
//|                      ☀️ 2026 RISK UPGRADE                        |
//|                        SURFER0073                                |
//+------------------------------------------------------------------+
//|        🎯 バランス型 - CB回転最大化 + リスク制御                    |
//|        📊 first_lot（残高/25000）                                 |
//|        🎯 RB=1.25 / max=8(hard) / DD20%制限                      |
//|        🛡️ v7.25: トレンドフィルター復活（ADX+ATRスマート版）       |
//|        🛡️ v7.25: ナンピン上限 15→8段 + DD%制限追加                |
//|        ✂️ v7.22: テール損切り（10段/$50/30分）                    |
//|        💹 v7.24: divisor 45000→25000（ロット約1.5倍・CB増加）     |
//+------------------------------------------------------------------+
#property copyright "SURFER0073"
#property link      ""
#property version   "7.25"
#property strict

#include <Trade\Trade.mqh>

//--- マジックナンバー・基本設定
input int    magic_number       = 77250001;  // マジックナンバー
input double divisor            = 25000;     // ロット計算除数（残高/divisor）
input double nanpin_width       = 5.0;       // ナンピン幅（ドル）
input double rb_ratio           = 1.25;      // RB利確倍率
input int    slippage           = 30;        // スリッページ（ポイント）

//--- ナンピン上限（v7.25: 動的上限）
input int    max_position_hard  = 8;         // ハードリミット（絶対上限）
input double max_dd_percent     = 20.0;      // 含み損率上限（%）でナンピン停止

//--- トレンドフィルター（v7.25: スマート版）
input bool   use_trend_filter   = true;      // トレンドフィルター使用
input int    adx_period         = 14;        // ADX期間
input double adx_threshold      = 30.0;      // ADXしきい値
input double atr_spike_ratio    = 1.5;       // ATRスパイク倍率
input int    atr_avg_period     = 20;        // ATR平均期間

//--- テール損切り（v7.22）
input bool   use_tail_cut       = true;      // テール損切り使用
input int    tail_cut_min_pos   = 10;        // テール損切り最小ポジション数
input double tail_cut_gap       = 50.0;      // テール損切り乖離額（ドル）
input int    tail_cut_interval  = 30;        // テール損切り間隔（分）
input int    tail_cut_max_daily = 5;         // テール損切り1日上限回数

//--- UIパネル
input bool   show_panel         = true;      // 情報パネル表示
input int    panel_x            = 10;        // パネルX座標
input int    panel_y            = 30;        // パネルY座標

//--- グローバル変数
CTrade trade;

int    h_adx       = INVALID_HANDLE;
int    h_atr       = INVALID_HANDLE;

double buy_lots[];       // BUYポジションのロット
double sell_lots[];      // SELLポジションのロット
double buy_prices[];     // BUYポジションの約定価格
double sell_prices[];    // SELLポジションの約定価格
ulong  buy_tickets[];    // BUYポジションのチケット
ulong  sell_tickets[];   // SELLポジションのチケット

datetime last_tail_cut_time = 0;       // 最後のテール損切り実行時間
int      daily_tail_cuts    = 0;       // 当日テール損切り回数
int      last_tail_cut_day  = 0;       // テール損切り日付追跡

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(magic_number);
   trade.SetDeviationInPoints(slippage);
   trade.SetTypeFilling(ORDER_FILLING_IOC);

   //--- ADXハンドル取得
   if(use_trend_filter)
   {
      h_adx = iADX(_Symbol, PERIOD_M1, adx_period);
      if(h_adx == INVALID_HANDLE)
      {
         Print("ERROR: ADXハンドル取得失敗");
         return INIT_FAILED;
      }
   }

   //--- ATRハンドル取得（トレンドフィルター用）
   h_atr = iATR(_Symbol, PERIOD_M1, adx_period);
   if(h_atr == INVALID_HANDLE)
   {
      Print("ERROR: ATRハンドル取得失敗");
      return INIT_FAILED;
   }

   Print("SUNRISE EA v7.25 BALANCED 初期化完了");
   Print("divisor=", divisor, " RB=", rb_ratio, " max_hard=", max_position_hard,
         " DD%=", max_dd_percent, " TrendFilter=", use_trend_filter);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(h_adx != INVALID_HANDLE) IndicatorRelease(h_adx);
   if(h_atr != INVALID_HANDLE) IndicatorRelease(h_atr);

   ObjectsDeleteAll(0, "SUN_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Expert tick function                                                |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- 日付変更チェック（テール損切り日次カウンタリセット）
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day_of_year != last_tail_cut_day)
   {
      daily_tail_cuts   = 0;
      last_tail_cut_day = dt.day_of_year;
   }

   //--- ポジション情報収集
   CollectPositions();

   int buy_count  = ArraySize(buy_tickets);
   int sell_count = ArraySize(sell_tickets);

   //--- 初回ロット計算
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double first_lot = NormalizeLot(balance / divisor);

   //--- 現在価格
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   //--- CB利確チェック（常に実行 - 方向問わず）
   CheckCBClose(true,  buy_count,  buy_tickets,  buy_prices,  buy_lots,  first_lot);
   CheckCBClose(false, sell_count, sell_tickets, sell_prices, sell_lots, first_lot);

   //--- テール損切りチェック
   if(use_tail_cut)
   {
      CheckTailCut(true,  buy_count,  buy_tickets,  buy_prices,  bid);
      CheckTailCut(false, sell_count, sell_tickets, sell_prices, ask);
   }

   //--- ナンピン／新規エントリー判定
   bool buy_blocked  = false;
   bool sell_blocked = false;

   //--- トレンドフィルターチェック
   if(use_trend_filter)
   {
      buy_blocked  = IsTrendBlocked(true);
      sell_blocked = IsTrendBlocked(false);
   }

   //--- DD%チェック
   bool dd_blocked = IsDDBlocked();

   //--- BUY側エントリー／ナンピン
   if(!buy_blocked && !dd_blocked)
   {
      if(buy_count == 0)
      {
         // 新規BUYエントリー
         trade.Buy(first_lot, _Symbol, ask, 0, 0, "SUN725_BUY_1");
      }
      else if(buy_count < max_position_hard)
      {
         // ナンピン判定: 最安BUY価格からnanpin_width以上下落したら追加
         double lowest_buy = FindLowestPrice(buy_prices);
         if(ask <= lowest_buy - nanpin_width)
         {
            double lot = first_lot;  // 均一ロット
            string comment = StringFormat("SUN725_BUY_%d", buy_count + 1);
            trade.Buy(lot, _Symbol, ask, 0, 0, comment);
         }
      }
   }

   //--- SELL側エントリー／ナンピン
   if(!sell_blocked && !dd_blocked)
   {
      if(sell_count == 0)
      {
         // 新規SELLエントリー
         trade.Sell(first_lot, _Symbol, bid, 0, 0, "SUN725_SELL_1");
      }
      else if(sell_count < max_position_hard)
      {
         // ナンピン判定: 最高SELL価格からnanpin_width以上上昇したら追加
         double highest_sell = FindHighestPrice(sell_prices);
         if(bid >= highest_sell + nanpin_width)
         {
            double lot = first_lot;  // 均一ロット
            string comment = StringFormat("SUN725_SELL_%d", sell_count + 1);
            trade.Sell(lot, _Symbol, bid, 0, 0, comment);
         }
      }
   }

   //--- UIパネル更新
   if(show_panel) UpdatePanel(buy_count, sell_count, buy_blocked, sell_blocked, dd_blocked);
}

//+------------------------------------------------------------------+
//| トレンドフィルター: この方向のナンピンをブロックすべきか判定         |
//| is_buy_side=true: BUY側ナンピンの判定                              |
//| 戻り値: true = ブロック（ナンピン禁止）                             |
//+------------------------------------------------------------------+
bool IsTrendBlocked(bool is_buy_side)
{
   if(!use_trend_filter || h_adx == INVALID_HANDLE || h_atr == INVALID_HANDLE)
      return false;

   //--- ADX値取得（メイン=ADX, +DI=バッファ1, -DI=バッファ2）
   double adx_val[1], plus_di[1], minus_di[1];
   if(CopyBuffer(h_adx, 0, 0, 1, adx_val) <= 0) return false;
   if(CopyBuffer(h_adx, 1, 0, 1, plus_di)  <= 0) return false;
   if(CopyBuffer(h_adx, 2, 0, 1, minus_di) <= 0) return false;

   //--- 条件A: ADX > しきい値
   if(adx_val[0] <= adx_threshold) return false;

   //--- ATR現在値取得
   double atr_val[1];
   if(CopyBuffer(h_atr, 0, 0, 1, atr_val) <= 0) return false;

   //--- ATR過去平均取得
   double atr_history[];
   ArrayResize(atr_history, atr_avg_period);
   if(CopyBuffer(h_atr, 0, 1, atr_avg_period, atr_history) < atr_avg_period) return false;

   double atr_sum = 0;
   for(int i = 0; i < atr_avg_period; i++)
      atr_sum += atr_history[i];
   double atr_avg = atr_sum / atr_avg_period;

   //--- 条件B: ATR > ATR平均 × スパイク倍率
   if(atr_val[0] <= atr_avg * atr_spike_ratio) return false;

   //--- 条件A かつ B 成立 → トレンド方向判定
   if(plus_di[0] > minus_di[0])
   {
      // 上昇トレンド → SELL側ナンピンをブロック
      return !is_buy_side;  // is_buy_side=false(SELL)ならtrue(ブロック)
   }
   else
   {
      // 下降トレンド → BUY側ナンピンをブロック
      return is_buy_side;   // is_buy_side=true(BUY)ならtrue(ブロック)
   }
}

//+------------------------------------------------------------------+
//| 含み損率チェック: DD%超過でナンピン停止                              |
//+------------------------------------------------------------------+
bool IsDDBlocked()
{
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   if(balance <= 0) return true;

   double floating = 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic_number) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      floating += PositionGetDouble(POSITION_PROFIT)
                + PositionGetDouble(POSITION_SWAP);
   }

   // 含み損（マイナス値）の絶対値で判定
   if(floating < 0)
   {
      double dd_pct = MathAbs(floating) / balance * 100.0;
      if(dd_pct > max_dd_percent) return true;
   }

   return false;
}

//+------------------------------------------------------------------+
//| CB利確チェック（クローズ＆バスケット決済）                           |
//+------------------------------------------------------------------+
void CheckCBClose(bool is_buy, int count, ulong &tickets[], double &prices[],
                  double &lots[], double first_lot)
{
   if(count < 2) return;  // 2ポジション以上で利確判定

   //--- 平均建値計算
   double total_lot   = 0;
   double total_cost  = 0;

   for(int i = 0; i < count; i++)
   {
      total_lot  += lots[i];
      total_cost += lots[i] * prices[i];
   }

   if(total_lot <= 0) return;
   double avg_price = total_cost / total_lot;

   //--- 利確目標: RB × first_lot × nanpin_width（ドル換算）
   double target_profit = rb_ratio * first_lot * nanpin_width;

   //--- 現在の合計含み損益
   double current_profit = 0;
   for(int i = 0; i < count; i++)
   {
      ulong ticket = tickets[i];
      if(!PositionSelectByTicket(ticket)) continue;
      current_profit += PositionGetDouble(POSITION_PROFIT)
                      + PositionGetDouble(POSITION_SWAP);
   }

   //--- 利確条件達成
   if(current_profit >= target_profit)
   {
      string side = is_buy ? "BUY" : "SELL";
      Print(StringFormat("CB利確 [%s] 合計損益=%.2f 目標=%.2f ポジ数=%d",
            side, current_profit, target_profit, count));

      // 全ポジション決済
      for(int i = 0; i < count; i++)
      {
         trade.PositionClose(tickets[i]);
      }
   }
}

//+------------------------------------------------------------------+
//| テール損切りチェック（v7.22）                                       |
//| 条件: ポジション数≧10 & 最遠ポジ乖離≧$50 & 間隔30分 & 1日5回     |
//+------------------------------------------------------------------+
void CheckTailCut(bool is_buy, int count, ulong &tickets[], double &prices[],
                  double current_price)
{
   if(count < tail_cut_min_pos) return;
   if(daily_tail_cuts >= tail_cut_max_daily) return;

   //--- 間隔チェック
   if(TimeCurrent() - last_tail_cut_time < tail_cut_interval * 60) return;

   //--- 最も不利なポジション（テール）を特定
   int    tail_idx   = -1;
   double worst_gap  = 0;

   for(int i = 0; i < count; i++)
   {
      double gap = 0;
      if(is_buy)
         gap = current_price - prices[i];  // BUY: 価格下落で損失（gapがマイナス=損失大）
      else
         gap = prices[i] - current_price;  // SELL: 価格上昇で損失（gapがマイナス=損失大）

      // 最も乖離が大きい（最も損失が大きい）ポジションを探す
      if(gap < worst_gap || tail_idx == -1)
      {
         worst_gap = gap;
         tail_idx  = i;
      }
   }

   if(tail_idx < 0) return;

   //--- 乖離がtail_cut_gap以上なら損切り
   if(MathAbs(worst_gap) >= tail_cut_gap)
   {
      string side = is_buy ? "BUY" : "SELL";
      Print(StringFormat("テール損切り [%s] 乖離=%.2f 段数=%d チケット=%d",
            side, worst_gap, count, tickets[tail_idx]));

      if(trade.PositionClose(tickets[tail_idx]))
      {
         last_tail_cut_time = TimeCurrent();
         daily_tail_cuts++;
      }
   }
}

//+------------------------------------------------------------------+
//| ポジション情報収集                                                  |
//+------------------------------------------------------------------+
void CollectPositions()
{
   ArrayResize(buy_tickets,  0);
   ArrayResize(buy_prices,   0);
   ArrayResize(buy_lots,     0);
   ArrayResize(sell_tickets,  0);
   ArrayResize(sell_prices,   0);
   ArrayResize(sell_lots,     0);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic_number) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      double price = PositionGetDouble(POSITION_PRICE_OPEN);
      double lot   = PositionGetDouble(POSITION_VOLUME);
      long   type  = PositionGetInteger(POSITION_TYPE);

      if(type == POSITION_TYPE_BUY)
      {
         int sz = ArraySize(buy_tickets);
         ArrayResize(buy_tickets, sz + 1);
         ArrayResize(buy_prices,  sz + 1);
         ArrayResize(buy_lots,    sz + 1);
         buy_tickets[sz] = ticket;
         buy_prices[sz]  = price;
         buy_lots[sz]    = lot;
      }
      else if(type == POSITION_TYPE_SELL)
      {
         int sz = ArraySize(sell_tickets);
         ArrayResize(sell_tickets, sz + 1);
         ArrayResize(sell_prices,  sz + 1);
         ArrayResize(sell_lots,    sz + 1);
         sell_tickets[sz] = ticket;
         sell_prices[sz]  = price;
         sell_lots[sz]    = lot;
      }
   }
}

//+------------------------------------------------------------------+
//| 最安値を返す                                                       |
//+------------------------------------------------------------------+
double FindLowestPrice(double &prices[])
{
   int size = ArraySize(prices);
   if(size == 0) return 0;
   double lowest = prices[0];
   for(int i = 1; i < size; i++)
      if(prices[i] < lowest) lowest = prices[i];
   return lowest;
}

//+------------------------------------------------------------------+
//| 最高値を返す                                                       |
//+------------------------------------------------------------------+
double FindHighestPrice(double &prices[])
{
   int size = ArraySize(prices);
   if(size == 0) return 0;
   double highest = prices[0];
   for(int i = 1; i < size; i++)
      if(prices[i] > highest) highest = prices[i];
   return highest;
}

//+------------------------------------------------------------------+
//| ロット正規化                                                       |
//+------------------------------------------------------------------+
double NormalizeLot(double lot)
{
   double min_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(lot < min_lot) lot = min_lot;
   if(lot > max_lot) lot = max_lot;

   lot = MathFloor(lot / lot_step) * lot_step;
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| UIパネル更新                                                       |
//+------------------------------------------------------------------+
void UpdatePanel(int buy_count, int sell_count,
                 bool buy_blocked, bool sell_blocked, bool dd_blocked)
{
   //--- 含み損益・DD%計算
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double floating = equity - balance;
   double dd_pct   = (balance > 0 && floating < 0) ? MathAbs(floating) / balance * 100.0 : 0;

   //--- トレンド状態文字列
   string trend_str = "OFF";
   if(use_trend_filter)
   {
      if(buy_blocked && sell_blocked)
         trend_str = "BOTH BLOCKED";
      else if(buy_blocked)
         trend_str = "↓ BUY BLOCKED / SELL OK";
      else if(sell_blocked)
         trend_str = "↑ BUY OK / SELL BLOCKED";
      else
         trend_str = "NORMAL (no strong trend)";
   }

   //--- DD制限状態
   string dd_str = dd_blocked ? "BLOCKED" : "OK";

   //--- パネルテキスト構築
   string text = "";
   text += "━━━ SUNRISE EA v7.25 BALANCED ━━━\n";
   text += StringFormat("Balance: $%.2f | Equity: $%.2f\n", balance, equity);
   text += StringFormat("Floating: $%.2f | DD: %.1f%%\n", floating, dd_pct);
   text += StringFormat("Lot: %.2f (Balance/%.0f)\n", NormalizeLot(balance / divisor), divisor);
   text += "───────────────────────────\n";
   text += StringFormat("BUY:  %d pos | SELL: %d pos\n", buy_count, sell_count);
   text += StringFormat("Hard Limit: %d | DD Limit: %.0f%%\n", max_position_hard, max_dd_percent);
   text += "───────────────────────────\n";
   text += StringFormat("TREND: %s\n", trend_str);
   text += StringFormat("DD CHECK: %s (%.1f%% / %.0f%%)\n", dd_str, dd_pct, max_dd_percent);
   text += StringFormat("Tail Cut: %d/%d today\n", daily_tail_cuts, tail_cut_max_daily);
   text += "━━━━━━━━━━━━━━━━━━━━━━━━━━";

   Comment(text);
}
//+------------------------------------------------------------------+
