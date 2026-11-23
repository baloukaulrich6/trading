// Indicateur de lecture du dernier état publié par robot.py.
#property indicator_chart_window
#property indicator_plots 0
input long MagicRobot = 20261121;

string ResumePositions(const string devise)
{
   string resume = "";
   double latent = 0.0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
         PositionGetInteger(POSITION_MAGIC) != MagicRobot)
         continue;
      double gain = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      latent += gain;
      string sens = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "achat" : "vente";
      resume += StringFormat("#%I64u %s %.4f lot | stop %s | %+.2f %s\n",
                             ticket, sens, PositionGetDouble(POSITION_VOLUME),
                             DoubleToString(PositionGetDouble(POSITION_SL), _Digits), gain, devise);
   }
   if(resume == "")
      resume = "Aucune position ouverte du robot sur ce symbole.\n";
   return resume + StringFormat("Latent : %+.2f %s\n", latent, devise);
}

string ResumeHistorique(const string devise)
{
   datetime maintenant = TimeCurrent();
   if(maintenant == 0 || !HistorySelect(maintenant - 30 * 86400, maintenant))
      return "Historique indisponible.";
   double net = 0.0;
   int total = HistoryDealsTotal();
   long dernier_type = -1;
   ulong dernier = 0;
   for(int i = 0; i < total; i++)
   {
      ulong deal = HistoryDealGetTicket(i);
      if(deal == 0 || HistoryDealGetString(deal, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(deal, DEAL_MAGIC) != MagicRobot)
         continue;
      net += HistoryDealGetDouble(deal, DEAL_PROFIT) + HistoryDealGetDouble(deal, DEAL_SWAP)
           + HistoryDealGetDouble(deal, DEAL_COMMISSION) + HistoryDealGetDouble(deal, DEAL_FEE);
      dernier = deal;
      dernier_type = HistoryDealGetInteger(deal, DEAL_ENTRY);
   }
   string resume = StringFormat("Historique robot (30 j) : %+.2f %s", net, devise);
   if(dernier != 0)
   {
      string action = dernier_type == DEAL_ENTRY_IN ? "entrée" : "sortie / modification";
      resume += StringFormat(" | dernier deal #%I64u (%s)", dernier, action);
   }
   return resume;
}

int OnInit()
{
   EventSetTimer(2);
   OnTimer();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Comment("");
}

void OnTimer()
{
   string symbole = "";
   for(int i = 0; i < StringLen(_Symbol); i++)
   {
      ushort c = StringGetCharacter(_Symbol, i);
      bool valide = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') ||
                    (c >= 'a' && c <= 'z') || c == '.' || c == '_' || c == '-';
      symbole += valide ? StringSubstr(_Symbol, i, 1) : "_";
   }
   string nom = "SuiviRobot\\" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) +
                "_" + symbole + ".txt";
   int fichier = FileOpen(nom, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI |
                          FILE_SHARE_READ | FILE_SHARE_WRITE, 0, CP_UTF8);
   string etat = "En attente d'un état publié par le robot.\n";
   if(fichier != INVALID_HANDLE)
   {
      etat = "";
      while(!FileIsEnding(fichier))
         etat += FileReadString(fichier) + "\n";
      FileClose(fichier);
   }
   string devise = AccountInfoString(ACCOUNT_CURRENCY);
   Comment("Robot MT5 | ", _Symbol, "\n", etat, "\n", ResumePositions(devise), ResumeHistorique(devise));
}

int OnCalculate(const int rates_total, const int prev_calculated, const int begin,
                const double &price[])
{
   return rates_total;
}
