#property copyright "Copyright 2016, Ricky Cook"
#property link      "https://github.com/RickyCook/mypanda-mt-remote"
#property version   "0.0.1"
#property strict

#include <stdlib.mqh>

#define ORDER_SLIPPAGE   3
#define ORDER_STOPLOSS   20
#define ORDER_TAKEPROFIT 20
#define SERVER_URL       "http://192.168.251.1/report"

#define BAR_URL          SERVER_URL + "?type=bar"
#define TICK_URL         SERVER_URL + "?type=tick"
#define ORDER_URL        SERVER_URL + "?type=order"

#define FORM_SEP         "--------ntoehuntaoedunoheut"
#define RPC_ARG_SEP      StringGetCharacter(",", 0)
#define RPC_CMD_SEP      StringGetCharacter("\n", 0)

int open_order(int signal, double volume) {
   double price, stoploss, takeprofit;

   switch(signal) {
   case OP_BUY:
      price = Ask;
      stoploss = NormalizeDouble(price - ORDER_STOPLOSS * Point, Digits);
      takeprofit = NormalizeDouble(price + ORDER_TAKEPROFIT * Point, Digits);
      break;
   case OP_SELL:
      price = Bid;
      stoploss = NormalizeDouble(price + ORDER_STOPLOSS * Point, Digits);
      takeprofit = NormalizeDouble(price - ORDER_TAKEPROFIT * Point, Digits);
      break;
   default:
      MessageBox("Unknown order type", "Error", MB_ICONEXCLAMATION);
      return -1;
   }

   return OrderSend(
      Symbol(),
      signal,
      volume,
      price,
      ORDER_SLIPPAGE,
      stoploss,
      takeprofit
   );
}

void handle_error(string url) {
   int error = GetLastError();
   Alert("Error " + (string)error + ": " + ErrorDescription(error));

   string message = NULL;

   switch(error) {
   case ERR_WEBREQUEST_INVALID_ADDRESS:
      message = "The URL '" + url + "' is invalid";
      break;
   case ERR_WEBREQUEST_CONNECT_FAILED:
      message = "Failed to connect to '" + url + "'. Make  sure the server is running";
      break;
   case ERR_WEBREQUEST_TIMEOUT:
      message = "Timed out waiting for a reply from '" + url + "'";
      break;
   case ERR_WEBREQUEST_REQUEST_FAILED:
      message = "Requesting '" + url + "' failed for an unknown reason";
      break;

   case ERR_FUNCTION_NOT_CONFIRMED:
      message = "In the dialog Tools > Options > Expert Advisors, add the URL '" +
         url + "' to the list of allowed URLs (see experts log for copyable URL)";
      break;
   }

   if (message != NULL) {
      Print(message);
      MessageBox(message, "Error", MB_ICONEXCLAMATION);
   }
}

int close_all_orders(int except_first_of = -1) {
   int errors = 0;
   int exceptions = 0;
   while (OrderSelect(errors + exceptions, SELECT_BY_POS, MODE_TRADES)) {
      if (OrderType() == except_first_of && exceptions < 1) {
        exceptions += 1;
        continue;
      }

      double price;
      if (OrderType() == OP_BUY)
         price = Bid;
      if (OrderType() == OP_SELL)
         price = Ask;

      if (!OrderClose(OrderTicket(), OrderLots(), price, ORDER_SLIPPAGE)) {
         MessageBox(
            "Unknown error closing order: " + GetLastError(),
            "Order Error",
            MB_ICONERROR
         );
         errors += 1;
      }
   }

   if (errors > 0)
      return -1;
   if (exceptions > 0)
      return 1;
   return 0;
}

void handle_rpc(char& result[]) {
   string result_str = CharArrayToString(result);

   string lines[];
   int num_lines = StringSplit(result_str, RPC_CMD_SEP, lines);

   for (int line_idx = 0; line_idx < num_lines; line_idx++) {
      string rpc_args[];
      int num_args = StringSplit(lines[line_idx], RPC_ARG_SEP, rpc_args);

      if (rpc_args[0] == "ORDER") {
         Print("Order RPC: ", rpc_args[1], rpc_args[2]);

         int signal = -1;
         if (rpc_args[1] == "buy") {
            signal = OP_BUY;
         } else if (rpc_args[1] == "sell") {
            signal = OP_SELL;
         } else if (rpc_args[1] == "out") {
         } else {
            MessageBox("Unknown order type '" + rpc_args[1] + "'", "Error", MB_ICONEXCLAMATION);
         }

         int close_success = close_all_orders(signal);

         char data[], order_result[];
         bool order_success = false;

         if (close_success < 0) {
            order_success = false;
         } else if (close_success > 0) {
            OrderSelect(0, SELECT_BY_POS, MODE_TRADES);
            if (OrderLots() != StringToDouble(rpc_args[2])) {
               MessageBox("Can't change lots/volume of an open order", "Error", MB_ICONEXCLAMATION);
               order_success = false;
            } else {
               order_success = true;
            }
         } else if (rpc_args[1] == "out") {
            order_success = true;
         } else {
            double volume = StringToDouble(rpc_args[2]);
            int ticket = open_order(signal, volume);

            if (ticket < 0) {
               string message;
               int error = GetLastError();

               switch (error) {
               case ERR_TRADE_NOT_ALLOWED:
                  message = "Trade is not allowed. Enable checkbox 'Allow live trading' in the Expert Advisor properties";
                  break;
               case ERR_INVALID_STOPS:
                  message = "Invalid stops. Minimum value is " + MarketInfo(Symbol(), MODE_STOPLEVEL);
                  break;
               default:
                  message = "Unknown trade error: " + error;
               }

               MessageBox(message, "Order Error", MB_ICONERROR);
               order_success = false;
            } else {
               order_success = true;
            }
         }

         if (order_success) {
            StringToCharArray("status=success", data);
         } else {
            StringToCharArray("status=error", data);
         }

         if (data[ArraySize(data) - 1] == '\0')
            ArrayResize(data, ArraySize(data) - 1);
         request("POST", ORDER_URL, data, order_result);
      } else {
         MessageBox("Unknown RPC command '" + rpc_args[0] + "'", "Error", MB_ICONERROR);
      }
   }
}

int request(string method, string url, char& data[], char& result[]) {
   string headers = NULL, result_headers = "";
   int status, timeout = 5000;

   ResetLastError();
   status = WebRequest(method, url, headers, timeout, data, result, result_headers);

   if (status == -1) {
      handle_error(SERVER_URL);
      return(-1);
   }

   handle_rpc(result);

   if (status < 200 || status > 299) {
      Alert("Error HTTP " + (string)status + ": only 2XX is acceptable");
      return(-1);
   }

   return(status);
}

int lastTime;

int OnInit() {
   lastTime = Time[1];

   char data[], result[];

   if (request("GET", SERVER_URL, data, result) == -1)
      return(INIT_FAILED);

   Print("Connected successfully");
   return(INIT_SUCCEEDED);
}

void OnTick() {
   sendTick();
   if (lastTime < Time[1])
      sendBar(1);
}

void sendTick() {
   char data[], result[];
   StringToCharArray(StringConcatenate(
       "tick_ts=", TimeCurrent(),
      "&price=",   Bid
   ), data);

   if (data[ArraySize(data) - 1] == '\0')
      ArrayResize(data, ArraySize(data) - 1);

   request("POST", TICK_URL, data, result);
}
void sendBar(int idx) {
   char data[], result[];
   StringToCharArray(StringConcatenate(
       "start_ts=", Time[idx],
      "&open_=",    Open[idx],
      "&high=",     High[idx],
      "&low=",      Low[idx],
      "&close=",    Close[idx],
      "&volume=",   Volume[idx]
   ), data);

   if (data[ArraySize(data) - 1] == '\0')
      ArrayResize(data, ArraySize(data) - 1);

   if (Time[idx] > lastTime)
      lastTime = Time[idx];

   request("POST", BAR_URL, data, result);
}
