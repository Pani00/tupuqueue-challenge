#!/usr/bin/env python3
"""
Actualiza data.json con el rango actual de SoloQ de cada jugador
listado en players.json, usando la API oficial de Riot Games.
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
REQUEST_DELAY = 1.2

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


def fetch_new_pentakills(puuid, continent, last_checked_match_id):
    match_ids = riot_get(
        f"https://{continent}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        f"?queue=420&start=0&count=20"
    )
    if not match_ids:
        return 0, last_checked_match_id
    if last_checked_match_id is None:
        return 0, match_ids[0]
    new_matches = match_ids[:match_ids.index(last_checked_match_id)] if last_checked_match_id in match_ids else match_ids
    pentas = 0
    for match_id in reversed(new_matches):
        time.sleep(REQUEST_DELAY)
        match = riot_get(f"https://{continent}.api.riotgames.com/lol/match/v5/matches/{match_id}")
        idx = match["metadata"]["participants"].index(puuid)
        pentas += match["info"]["participants"][idx].get("pentaKills", 0)
    return pentas, match_ids[0]

def fetch_last_game(puuid, continent):
    """Devuelve info de la última partida ranked."""
    try:
        match_ids = riot_get(
            f"https://{continent}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
            f"?queue=420&start=0&count=1"
        )
        if not match_ids:
            return None
        match = riot_get(f"https://{continent}.api.riotgames.com/lol/match/v5/matches/{match_ids[0]}")
        idx = match["metadata"]["participants"].index(puuid)
        p = match["info"]["participants"][idx]
        return {
            "win": p.get("win", False),
            "championId": p.get("championId"),
            "championName": p.get("championName"),
            "kills": p.get("kills", 0),
            "deaths": p.get("deaths", 0),
            "assists": p.get("assists", 0),
            "gameEndTimestamp": match["info"].get("gameEndTimestamp"),
        }
    except Exception:
        return None


def fetch_current_game(puuid, platform):
    """Devuelve info si el jugador está en partida ahora."""
    try:
        game = riot_get(
            f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        )
        participant = next((p for p in game.get("participants", []) if p.get("puuid") == puuid), None)
        if not participant:
            return None
        return {
            "championId": participant.get("championId"),
            "gameLength": game.get("gameLength", 0),
            "gameQueueConfigId": game.get("gameQueueConfigId"),
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # no está en partida
        return None
    except Exception:
        return None

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

                       continent = PLATFORM_TO_CONTINENT.get(platform, "americas")
            last_match_id = prev_player.get("lastMatchId")
            new_pentas, newest_match_id = fetch_new_pentakills(
                fetched["puuid"], continent, last_match_id
            )
            total_pentas = (prev_player.get("pentakills") or 0) + new_pentas

            # Nueva parte: última partida + si está en juego
            last_game = fetch_last_game(fetched["puuid"], continent)
            time.sleep(REQUEST_DELAY)
            current_game = fetch_current_game(fetched["puuid"], platform)

            players_out.append({
                "gameName": entry["gameName"],
                "tagLine": entry["tagLine"],
                "opggUrl": opgg_url,
                "updatedAt": now_iso,
                "stale": False,
                "baseline": baseline,
                "pentakills": total_pentas,
                "lastMatchId": newest_match_id,
                "lastGame": last_game,
                "inGame": current_game,
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
