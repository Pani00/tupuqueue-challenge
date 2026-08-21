#!/usr/bin/env python3
"""
Actualiza data.json con el rango actual de SoloQ de cada jugador
listado en players.json, usando la API oficial de Riot Games.

Se ejecuta automáticamente cada 30 minutos vía GitHub Actions
(.github/workflows/update.yml), pero también se puede correr a mano:

    RIOT_API_KEY=tu_api_key python3 fetch_data.py

Requiere únicamente la librería estándar de Python (sin pip install).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PLAYERS_FILE = "players.json"
DATA_FILE = "data.json"
REQUEST_DELAY = 1.2  # segundos entre llamadas a la API, para no pegarle al rate limit

PLATFORM_TO_CONTINENT = {
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
    "kr": "asia", "jp1": "asia",
    "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea",
}

PLATFORM_TO_OPGG_REGION = {
    "la2": "las", "la1": "lan", "na1": "na", "br1": "br", "euw1": "euw",
    "eun1": "eune", "kr": "kr", "jp1": "jp", "oc1": "oce", "tr1": "tr", "ru": "ru",
}

API_KEY = os.environ.get("RIOT_API_KEY")


def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)


def riot_get(url):
    req = urllib.request.Request(
        url,
        headers={
            "X-Riot-Token": API_KEY,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_latest_ddragon_version(fallback=None):
    try:
        req = urllib.request.Request("https://ddragon.leagueoflegends.com/api/versions.json")
        with urllib.request.urlopen(req, timeout=15) as resp:
            versions = json.loads(resp.read().decode("utf-8"))
            return versions[0]
    except Exception as e:
        log(f"No se pudo obtener la versión de DDragon, uso la anterior: {e}")
        return fallback


def fetch_player(game_name, tag_line, platform):
    continent = PLATFORM_TO_CONTINENT.get(platform, "americas")
    encoded_name = urllib.parse.quote(game_name)
    encoded_tag = urllib.parse.quote(tag_line)

    account = riot_get(
        f"https://{continent}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}"
    )
    puuid = account["puuid"]
    time.sleep(REQUEST_DELAY)

    summoner = riot_get(
        f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    )
    time.sleep(REQUEST_DELAY)

    entries = riot_get(
        f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    )
    solo = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)

    result = {
        "puuid": puuid,
        "profileIconId": summoner.get("profileIconId"),
        "summonerLevel": summoner.get("summonerLevel"),
    }
    if solo:
        result.update({
            "tier": solo["tier"],
            "rank": solo["rank"],
            "leaguePoints": solo["leaguePoints"],
            "wins": solo["wins"],
            "losses": solo["losses"],
        })
    else:
        result.update({
            "tier": None, "rank": None, "leaguePoints": 0, "wins": 0, "losses": 0,
        })
    return result


def main():
    if not API_KEY:
        log("ERROR: falta la variable de entorno RIOT_API_KEY")
        sys.exit(1)

    with open(PLAYERS_FILE, encoding="utf-8") as f:
        config = json.load(f)
    platform = config["region"]
    roster = config["players"]
    opgg_region = PLATFORM_TO_OPGG_REGION.get(platform, platform)

    previous = {"players": [], "ddragonVersion": None}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            previous = json.load(f)
    previous_by_key = {
        f"{p.get('gameName','')}#{p.get('tagLine','')}".lower(): p
        for p in previous.get("players", [])
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    ddragon_version = get_latest_ddragon_version(previous.get("ddragonVersion"))

    players_out = []
    for entry in roster:
        key = f"{entry['gameName']}#{entry['tagLine']}".lower()
        prev_player = previous_by_key.get(key, {})
        opgg_url = "https://op.gg/es/lol/summoners/{}/{}-{}".format(
            opgg_region,
            urllib.parse.quote(entry["gameName"]),
            urllib.parse.quote(entry["tagLine"]),
        )

        try:
            fetched = fetch_player(entry["gameName"], entry["tagLine"], platform)
            log(f"OK  {key}: {fetched.get('tier')} {fetched.get('rank')} {fetched.get('leaguePoints')} LP")

            baseline = prev_player.get("baseline")
            if not baseline:
                baseline = {
                    "tier": fetched["tier"],
                    "rank": fetched["rank"],
                    "leaguePoints": fetched["leaguePoints"],
                    "wins": fetched["wins"],
                    "losses": fetched["losses"],
                    "recordedAt": now_iso,
                }

            players_out.append({
                "gameName": entry["gameName"],
                "tagLine": entry["tagLine"],
                "opggUrl": opgg_url,
                "updatedAt": now_iso,
                "stale": False,
                "baseline": baseline,
                **fetched,
            })
        except urllib.error.HTTPError as e:
            log(f"FALLÓ {key}: HTTP {e.code} {e.reason}")
            players_out.append(_stale_entry(entry, opgg_url, prev_player, f"HTTP {e.code}"))
        except Exception as e:
            log(f"FALLÓ {key}: {e}")
            players_out.append(_stale_entry(entry, opgg_url, prev_player, str(e)))

        time.sleep(REQUEST_DELAY)

    output = {
        "generatedAt": now_iso,
        "ddragonVersion": ddragon_version,
        "players": players_out,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    log("data.json actualizado")


def _stale_entry(entry, opgg_url, prev_player, error):
    """Si falla una consulta, mantiene el último dato bueno en vez de borrar al jugador."""
    if prev_player:
        stale = dict(prev_player)
        stale["stale"] = True
        stale["error"] = error
        return stale
    return {
        "gameName": entry["gameName"],
        "tagLine": entry["tagLine"],
        "opggUrl": opgg_url,
        "stale": True,
        "error": error,
        "tier": None, "rank": None, "leaguePoints": 0, "wins": 0, "losses": 0,
    }


if __name__ == "__main__":
    main()
