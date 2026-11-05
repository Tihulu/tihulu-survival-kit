# SPDX-License-Identifier: AGPL-3.0-only
"""News Center local Translator/AI task coordinator; no actual model or APIs.

This is an internal, dependency-injected backend component. All article inputs
must come from authenticated, permission-checked source adapters. Do not expose
this module as an unauthenticated network endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
import secrets

from .news_source_scanner import MEDIA, InputPreferences
from .service_manager import ServiceManager


@dataclass(frozen=True)
class NewsText:
    """Source-grounded text, not an independently verified factual claim."""
    item_id: str
    source_id: str
    medium: str
    title: str
    original_text: str
    language: str
    published_at: str
    provenance: str
    source_type: str = "source_report"
    # A DVB page number or source URL is optional, but real provenance is not.
    source_locator: str = ""


@dataclass(frozen=True)
class NewsAssistRequest:
    item_ids: tuple[str, ...]
    translate_to: tuple[str, ...] = ()
    summaries: bool = False
    question: str | None = None
    compare_sources: bool = False
    ai_language: str = "en"


@dataclass(frozen=True)
class NewsAssistResult:
    translated: dict[str, dict[str, str]] = field(default_factory=dict)
    summaries: dict[str, str] = field(default_factory=dict)
    answers: str | None = None
    comparison: str | None = None
    # AI outputs are model-generated, not factual verification.
    attribution: str = "Generated from selected source texts; verify original sources."


class TranslatorEngine(Protocol):
    """Trusted local-only translator with installed language-pair knowledge."""
    def supports(self, source_language: str, target_language: str) -> bool: ...
    def translate(self, text: str, source_language: str, target_language: str) -> str: ...


class LocalAIEngine(Protocol):
    """Trusted local-only LLM; caller supplies source-attributed inputs."""
    def supports_language(self, language: str) -> bool: ...
    def summarize(self, text: str, language: str, source_label: str) -> str: ...
    def answer(self, question: str, materials: tuple[tuple[str, str], ...],
               language: str, *, compare: bool = False) -> str: ...


class NewsAssistCoordinator:
    """Explicit multi-item, multi-language operation using shared Stage-4 leases.

    News, Translator and Local AI have *separate* optional service policies.
    Work starts only with explicit owner interaction, not simply on News opening.
    Workers are released even if a translation or AI operation fails.
    """

    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager

    @staticmethod
    def _validate(request: NewsAssistRequest, articles: list[NewsText],
                  preferences: InputPreferences) -> list[NewsText]:
        if not request.item_ids or len(request.item_ids) > 12:
            raise ValueError("Select 1-12 articles for one task")
        if len(set(request.item_ids)) != len(request.item_ids):
            raise ValueError("Duplicate article selection")
        if len(request.translate_to) > 3 or len(set(request.translate_to)) != len(request.translate_to):
            raise ValueError("Select at most three distinct translation languages")
        langs = (request.translate_to + (request.ai_language,))
        if any(not x or len(x) > 12 or not x.replace("-", "").isalpha() for x in langs):
            raise ValueError("Invalid language identifier")
        if request.question is not None and (not request.question.strip()
                                             or len(request.question) > 2000):
            raise ValueError("Questions must be nonempty and at most 2000 characters")
        if request.compare_sources and len(request.item_ids) < 2:
            raise ValueError("Comparison needs at least two items")
        if not (request.translate_to or request.summaries
                or request.question or request.compare_sources):
            raise ValueError("Select translation or at least one AI action")
        items = {a.item_id: a for a in articles}
        if len(items) != len(articles):
            raise ValueError("Duplicate provided text items")
        if not set(request.item_ids).issubset(items):
            raise ValueError("Requested article unavailable")
        result = [items[item_id] for item_id in request.item_ids]
        if request.compare_sources and len({a.source_id for a in result}) < 2:
            raise ValueError("Compare at least two different sources")
        if not preferences.enabled_media.issubset(MEDIA):
            raise ValueError("Invalid source media")
        for a in result:
            if (not a.source_id or a.source_id not in preferences.selected_source_ids
                    or a.medium not in preferences.enabled_media
                    or not a.item_id or not a.provenance
                    or not a.published_at or not a.original_text.strip()
                    or not a.language or not a.title
                    or len(a.original_text) > 24000):
                raise PermissionError("Only selected, attributed source texts may be processed")
        return result

    def process(self, request: NewsAssistRequest, articles: list[NewsText],
                preferences: InputPreferences, *,
                owner_id: str, explicit_user_action: bool = False,
                translator: TranslatorEngine | None = None,
                ai: LocalAIEngine | None = None) -> NewsAssistResult:
        if not explicit_user_action or not owner_id:
            raise PermissionError("A verified owner-initiated analysis request is required")
        selected = self._validate(request, articles, preferences)
        ai_needed = bool(request.summaries or request.question or request.compare_sources)
        if ai_needed and ai is None:
            raise RuntimeError("Local AI backend is not installed")
        translation_pairs: set[tuple[str, str]] = set()
        for article in selected:
            for lang in request.translate_to:
                if lang != article.language:
                    translation_pairs.add((article.language, lang))
            if ai_needed and article.language != request.ai_language:
                translation_pairs.add((article.language, request.ai_language))
        if ai_needed and not ai.supports_language(request.ai_language):
            raise RuntimeError("Selected local AI model does not support the analysis language")
        if translation_pairs:
            if translator is None:
                raise RuntimeError("Local Translator backend is not installed")
            for src, dest in translation_pairs:
                if not translator.supports(src, dest):
                    raise RuntimeError("Required offline translation language pair is unavailable")
        # Keep leases independent. News views may close; an explicit server job
        # can be used by the future Task Center to preserve these worker leases.
        task_prefix = secrets.token_urlsafe(12)
        leases: list[str] = []
        try:
            if translation_pairs:
                task_id = "news-translate:" + task_prefix
                self.service_manager.acquire("translator", task_id=task_id,
                                             owner_id=owner_id)
                leases.append(task_id)
            if ai_needed:
                task_id = "news-ai:" + task_prefix
                self.service_manager.acquire("local_ai", task_id=task_id,
                                             owner_id=owner_id)
                leases.append(task_id)
            translated: dict[str, dict[str, str]] = {}
            summaries: dict[str, str] = {}
            materials: list[tuple[str, str]] = []
            for article in selected:
                versions: dict[str, str] = {}
                for lang in request.translate_to:
                    versions[lang] = (article.original_text if lang == article.language
                                      else translator.translate(article.original_text,
                                                                article.language, lang))
                translated[article.item_id] = versions
                if ai_needed:
                    # Translation-only requests must not trigger an unrelated
                    # conversion to the AI analysis language or load an LLM.
                    prepared = (versions[request.ai_language]
                                if request.ai_language in versions else
                                article.original_text if article.language == request.ai_language
                                else translator.translate(article.original_text,
                                                          article.language, request.ai_language))
                    # The original source identity, publisher type, original
                    # language, time and locator remain visible to the model.
                    label = (f"{article.source_id} | {article.title} | "
                             f"{article.source_type} | {article.medium} | "
                             f"published={article.published_at} | "
                             f"original-language={article.language} | "
                             f"origin={article.provenance} | {article.source_locator}")
                    if request.summaries:
                        summaries[article.item_id] = ai.summarize(
                            prepared, request.ai_language, label)
                    materials.append((label, prepared))
            answer = (ai.answer(request.question, tuple(materials), request.ai_language)
                      if request.question is not None else None)
            comparison = (ai.answer(
                "Compare the documented statements and common facts across these sources. "
                "Attribute claims to their sources. Do not rank political actors, "
                "recommend a political choice, or portray an unverified claim as fact.",
                tuple(materials), request.ai_language, compare=True)
                if request.compare_sources else None)
            return NewsAssistResult(translated, summaries, answer, comparison)
        finally:
            for task_id in reversed(leases):
                self.service_manager.release(task_id, owner_id=owner_id)
            # Actual idle-stop is handled by the Stage 4 supervisor/timer;
            # no always-resident model or news worker is launched here.
