# ============================================
# Project: playwright_scraper_pro
# File: scraper.py
# Author: Leox433
# Method: AI
# Version: V1.5
# Last modified: 2025-12-21 23:05 CET
# ============================================

import os
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Any
from playwright.sync_api import sync_playwright
from xhr_enricher import XHREnricher

REVIEWS_CONTAINER = "div.m6QErb.DxyBCb.kA9KIf.dS8AEf"
REVIEW_CARD = "div.jftiEf"

# -------------------------------------------------
# Utils
# -------------------------------------------------

def clean_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^\x00-\x7F]+", " ", text)
    return cleaned.strip().replace("\n", " ")

def _norm_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def _dom_stars(el) -> int | None:
    try:
        rating_el = el.locator("span.kvMYJc").first
        if rating_el.count() == 0:
            return None
        aria = rating_el.get_attribute("aria-label") or ""
        m = re.search(r"(\d)", aria)
        return int(m.group(1)) if m else None
    except:
        return None

def extract_price_range(page) -> str | None:
    try:
        price_el = page.locator(
            "span",
            has_text=re.compile(r"\d+\s*-\s*\d+\s*€")
        ).first
        if price_el.count() > 0:
            return price_el.inner_text().replace("\xa0", " ").strip()
    except:
        pass
    return None

def _safe_inner_text(locator) -> str:
    try:
        if locator.count() > 0:
            return locator.first.inner_text()
    except:
        pass
    return ""

def _dom_review_text_strict(el) -> str:
    """
    Devuelve SOLO el texto de usuario, excluyendo respuestas del propietario.
    """
    try:
        texts = el.locator(".wiI7pd")
        for i in range(texts.count()):
            node = texts.nth(i)
            if node.locator("xpath=ancestor::*[contains(@class,'CDe7pd')]").count() > 0:
                continue
            t = _safe_inner_text(node).strip()
            if t:
                return t
    except:
        pass
    return ""

def _extract_owner_reply(el) -> tuple[str | None, str | None]:
    try:
        owner_block = el.locator(".CDe7pd")
        if owner_block.count() == 0:
            return None, None

        txt = _safe_inner_text(owner_block.locator(".wiI7pd")).strip()
        dt = _safe_inner_text(owner_block.locator(".DZSIDd")).strip()

        if not txt:
            return None, None
        return txt, (dt or None)
    except:
        return None, None

def _safe_float(s: str) -> float | None:
    try:
        if not s:
            return None
        return float(s.replace(",", ".").strip())
    except:
        return None

def _safe_int_from_text(s: str) -> int:
    if not s:
        return 0
    m = re.search(r"([\d\.\,]+)", s)
    if not m:
        return 0
    raw = m.group(1)
    raw = raw.replace(".", "").replace(",", "")
    try:
        return int(raw)
    except:
        return 0

def _export_final_json(place_title: str, payload: dict) -> str:
    safe_name = re.sub(r'[\\/*?:"<>|]', "", (place_title or "place").replace(" ", "_"))
    os.makedirs("output", exist_ok=True)
    path = os.path.join("output", f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ Extracción finalizada: {path}")
    return path

def _pick(obj: Dict[str, Any], key: str, default=None):
    v = obj.get(key, default)
    return default if v is None else v

# -------------------------------------------------
# PLACE FEATURES (INFORMACIÓN)
# -------------------------------------------------

def extract_place_features(page) -> Dict[str, list | str]:
    features: Dict[str, list | str] = {}

    desc = page.locator("span.HlvSq")
    if desc.count() > 0:
        features["description"] = desc.first.inner_text().strip()

    sections = page.locator("div.iP2t7d")
    for i in range(sections.count()):
        section = sections.nth(i)
        title_el = section.locator("h2.iL3Qke")
        if title_el.count() == 0:
            continue

        title = title_el.inner_text().strip()
        values: List[str] = []

        items = section.locator("li.hpLkke span[aria-label]")
        for j in range(items.count()):
            txt = items.nth(j).inner_text().strip()
            if txt:
                values.append(txt)

        if values:
            features[title] = values

    return features

# -------------------------------------------------
# Main
# -------------------------------------------------

def run_scraper(share_url: str, target_reviews: int):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="es-ES"
        )
        page = context.new_page()

        xhr = XHREnricher()
        page.on("response", xhr.response_listener)

        # Salida final A+B
        output: Dict[str, object] = {
            "place": {},
            "reviews": []
        }

        page.goto(share_url, wait_until="domcontentloaded", timeout=60000)

        # --- Cookies ---
        try:
            page.wait_for_timeout(2000)
            cookie_button = page.locator("#L2AGLb").or_(
                page.get_by_role("button", name=re.compile("Aceptar|Accept", re.I))
            )
            if cookie_button.count() > 0:
                cookie_button.first.click()
        except:
            pass

        page.wait_for_selector("h1", timeout=15000)

        # --- Métricas base ---
        count_locator = page.locator(".jANrlb").get_by_text(
            re.compile(r"reseña|review", re.I)
        )
        raw_count_text = ""
        try:
            raw_count_text = count_locator.first.inner_text()
        except:
            raw_count_text = "0"

        price_range = extract_price_range(page)

        title = ""
        try:
            title = page.locator("h1").first.inner_text()
        except:
            title = ""

        address = ""
        try:
            if page.locator("button[data-item-id='address']").count():
                address = clean_text(page.locator("button[data-item-id='address']").inner_text())
        except:
            address = ""

        total_score = None
        try:
            total_score = _safe_float(page.locator(".fontDisplayLarge").first.inner_text())
        except:
            total_score = None

        category = ""
        try:
            if page.locator("button[jsaction*='category']").count():
                category = page.locator("button[jsaction*='category']").first.inner_text()
        except:
            category = ""

        website = ""
        try:
            if page.locator("a[data-item-id='authority']").count():
                website = clean_text(page.locator("a[data-item-id='authority']").inner_text())
        except:
            website = ""

        fid = None
        try:
            m = re.search(r"0x[0-9a-f]+:0x[0-9a-f]+", page.url)
            fid = m.group(0) if m else None
        except:
            fid = None

        phone = None
        try:
            if page.locator("button[data-item-id^='phone']").count():
                phone = clean_text(page.locator("button[data-item-id^='phone']").inner_text())
        except:
            phone = None

        place_meta = {
            "title": title,
            "address": address,
            "totalScore": total_score,
            "reviewsCount": _safe_int_from_text(raw_count_text),
            "priceRange": price_range,
            "category": category,
            "website": website,
            "fid": fid,
            "phoneNumber": phone,
            "url": page.url,
            "scrapedAt": datetime.now().isoformat() + "Z",
        }

        # --- Abrir pestaña INFORMACIÓN ---
        try:
            info_tab = page.locator("button[role='tab'][data-tab-index='3']")
            if info_tab.count() > 0:
                info_tab.first.click()
                page.wait_for_timeout(1500)
        except:
            pass

        place_meta["features"] = extract_place_features(page)

        # Guardar place una sola vez (A)
        output["place"] = place_meta

        # -------------------------------------------------
        # IR A RESEÑAS (FORZADO Y ESTABLE)
        # -------------------------------------------------
        try:
            reviews_tab = page.locator("button[role='tab'][data-tab-index='2']")
            if reviews_tab.count() > 0:
                reviews_tab.first.click()
                page.wait_for_selector(REVIEWS_CONTAINER, timeout=15000)
        except:
            pass

        page.wait_for_timeout(1500)

        # Ordenar por más recientes (si existe)
        try:
            sort_btn = page.get_by_role("button", name=re.compile("Ordenar", re.I))
            if sort_btn.count() > 0:
                sort_btn.first.click()
                page.wait_for_timeout(800)
                page.get_by_role("menuitemradio", name=re.compile("Más recientes", re.I)).click()
                page.wait_for_timeout(1500)
        except:
            pass

        # --- Scroll ---
        last_count = 0
        while True:
            page.locator(REVIEWS_CONTAINER).evaluate("el => el.scrollTo(0, el.scrollHeight)")
            page.wait_for_timeout(2000)

            curr = page.locator(REVIEW_CARD).count()
            if curr >= target_reviews:
                break
            if curr == last_count:
                break
            last_count = curr

        # --- Fusión XHR ---
        xhr_parsed = xhr.parse()
        xhr_by_id = xhr_parsed.get("by_id", {}) if isinstance(xhr_parsed, dict) else {}

        xhr_by_text: Dict[str, List[dict]] = {}
        for obj in xhr_by_id.values():
            t = _norm_text(obj.get("text", ""))
            if t:
                xhr_by_text.setdefault(t, []).append(obj)

        seen_review_ids: set[str] = set()

        # --- Loop reseñas ---
        for el in page.locator(REVIEW_CARD).all():
            if len(output["reviews"]) >= target_reviews:
                break

            rid = el.get_attribute("data-review-id")
            if not rid:
                continue
            if rid in seen_review_ids:
                continue

            dom_text = _dom_review_text_strict(el)
            dom_text_n = _norm_text(dom_text)
            dom_stars = _dom_stars(el)

            info = xhr_by_id.get(rid)

            # Fallback por texto+stars (cuando el XHR no trae esa ID o la UI no tiene data-review-id consistente)
            if not info and dom_text_n and dom_text_n in xhr_by_text:
                candidates = xhr_by_text[dom_text_n]
                if len(candidates) > 1 and dom_stars is not None:
                    info = next((c for c in candidates if c.get("stars") == dom_stars), candidates[0])
                else:
                    info = candidates[0]

            if not info:
                info = {"reviewId": rid}

            # URL de reseña (útil para auditoría)
            review_url = (
                "https://www.google.com/maps/reviews/data=!4m8!14m7!"
                f"1m6!2m5!1s{rid}!2m1!1s0x0:0x0!3m1!1s2@1?hl=es-ES"
            )

            # Owner reply (DOM) como refuerzo (si no venía en XHR)
            owner_txt, owner_dt = _extract_owner_reply(el)

            # -------------------------------------------------
            # ✅ CONSOLIDACIÓN FINAL (XHR manda, DOM rellena huecos)
            # - Incluye TODOS los campos XHR disponibles (no se pierden)
            # - DOM solo completa: text, stars, owner reply (si faltan)
            # - Permite reseñas sin texto si tienen métricas enterprise
            # -------------------------------------------------

            # Texto final: prioriza XHR; fallback DOM estricto
            final_text = (info.get("text") or dom_text or "").strip()

            # Stars final: prioriza XHR; fallback DOM
            final_stars = info.get("stars") if info.get("stars") is not None else dom_stars

            # Owner reply: prioriza XHR; fallback DOM
            final_owner_text = info.get("responseFromOwnerText") or owner_txt
            final_owner_date = info.get("responseFromOwnerDate") or owner_dt

            # Enterprise mínimo para aceptar reseñas sin texto
            has_enterprise_metrics = bool(final_stars) and bool(info.get("publishedAtDate"))

            # Si no hay texto, solo descartamos si tampoco hay (stars AND publishedAtDate)
            if not final_text and not has_enterprise_metrics:
                continue

            # Anti owner-as-review solo si hay texto
            if final_text and final_owner_text and _norm_text(final_text) == _norm_text(final_owner_text):
                continue

            # Base: clonar XHR tal cual para NO perder campos
            final_review = dict(info)

            # Forzar campos clave / auditoría / fallbacks
            final_review["reviewId"] = final_review.get("reviewId") or rid
            final_review["reviewUrl"] = final_review.get("reviewUrl") or review_url
            final_review["text"] = final_text  # puede ser ""
            final_review["stars"] = final_stars
            final_review["responseFromOwnerText"] = final_owner_text
            final_review["responseFromOwnerDate"] = final_owner_date
            final_review["scrapedAt"] = datetime.now().isoformat() + "Z"

            seen_review_ids.add(rid)
            output["reviews"].append(final_review)

        _export_final_json(place_meta.get("title", "place"), output)
        browser.close()
