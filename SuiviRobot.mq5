// Indicateur de lecture du dernier état publié par robot.py.
#property indicator_chart_window
#property indicator_plots 0

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
   if(fichier == INVALID_HANDLE)
   {
      Comment("Robot MT5 | ", _Symbol, "\nEn attente d'un état publié par le robot.");
      return;
   }
   string etat = "";
   while(!FileIsEnding(fichier))
      etat += FileReadString(fichier) + "\n";
   FileClose(fichier);
   Comment("Robot MT5 | ", _Symbol, "\n", etat);
}

int OnCalculate(const int rates_total, const int prev_calculated, const int begin,
                const double &price[])
{
   return rates_total;
}
