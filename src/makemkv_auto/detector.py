"""Advanced content type detection for Blu-ray/DVD discs."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from pathlib import Path

from makemkv_auto.logger import get_logger
from makemkv_auto.config import Config

logger = get_logger(__name__)


class ContentType(Enum):
    """Content type enumeration."""
    MOVIE = "movie"
    TV_SHOW = "tvshow"
    UNKNOWN = "unknown"


# Known TV shows that have movie-length episodes (60-120 min)
# These are often misdetected as movies
KNOWN_TV_SHOWS = {
    # Detective/Mystery series with feature-length episodes
    'miss marple',
    'agatha christie',
    'poirot',
    'hercule poirot',
    'sherlock',
    'sherlock holmes',
    'midsomer murders',
    'inspector morse',
    'lewis',
    'endeavour',
    'inspector lewis',
    'vera',
    'shetland',
    'broadchurch',
    'line of duty',
    'happy valley',
    'fargo',
    'true detective',
    'the killing',
    'wallander',
    'inspector montalbano',
    'commissario montalbano',
    'donna leon',
    'bruno',
    'dicte',
    'the bridge',
    'bron',
    'young wallander',
    
    # Anthology series
    'black mirror',
    'inside no. 9',
    'love death and robots',
    'electric dreams',
    'twilight zone',
    'tales from the loop',
    ' cabinet of curiosities',
    
    # Miniseries (often movie-length per episode)
    'band of brothers',
    'the pacific',
    'generation kill',
    'chernobyl',
    'the queen',
    'crown',
    'manhunt',
    'when they see us',
    'sharp objects',
    'big little lies',
    'mare of easttown',
    'night manager',
    'little dorrit',
    'bleak house',
    'pride and prejudice',
    'north and south',
    'jane eyre',
    'wuthering heights',
    'tess of the',
    'vanity fair',
    'david copperfield',
    'oliver twist',
    'great expectations',
    
    # British series with long episodes
    'downton abbey',
    'upstairs downstairs',
    'the crown',
    'victoria',
    'the durrells',
    'grantchester',
    'father brown',
    'sister boniface',
    'murdoch mysteries',
    'rosehaven',
    'death in paradise',
    'marcella',
    'the fall',
    'prime suspect',
    'cracker',
    'wire in the blood',
    'silent witness',
    'new tricks',
    'as time goes by',
    'last tango in halifax',
    'happy valley',
    
    # Nordic noir
    'the killing',
    'forbrydelsen',
    'borgia',
    'the borgias',
    'medici',
    'versailles',
    'vikings',
    'the last kingdom',
    'tudors',
    'the tudors',
    'white queen',
    'white princess',
    'spanish princess',
    'pillars of the earth',
    'world without end',
    'spartacus',
    'rome',
    
    # Premium cable series
    'game of thrones',
    'house of the dragon',
    'westworld',
    'watchmen',
    ' His Dark Materials',
    'the golden compass',
    'da vinci',
    'the borgias',
    'the white queen',
    'the white princess',
    'versailles',
    'the crown',
    'outlander',
    'vikings',
    'the last kingdom',
    
    # Period dramas
    'mad men',
    'the americans',
    'halt and catch fire',
    'better call saul',
    'breaking bad',
    'the sopranos',
    'the wire',
    'boardwalk empire',
    'homeland',
    'house of cards',
    'the morning show',
    'succession',
}


@dataclass
class TitleInfo:
    """Information about a single title."""
    index: int
    duration: int  # seconds
    size_bytes: int
    content_type: str = "unknown"


@dataclass 
class DetectionResult:
    """Result of content type detection."""
    content_type: ContentType
    confidence: str  # high, medium, low
    reason: str  # Explanation of the decision
    suggested_name: Optional[str] = None  # Cleaned name without episode info


class SmartContentDetector:
    """
    Advanced detector for distinguishing movies from TV shows.
    """
    
    def __init__(self, config: Config, min_episode_duration: int = 15, 
                 max_episode_duration: int = 70, min_movie_duration: int = 60) -> None:
        self.config = config
        self.min_episode_duration = min_episode_duration
        self.max_episode_duration = max_episode_duration
        self.min_movie_duration = min_movie_duration
    
    def detect(self, titles: list[TitleInfo], disc_name: str) -> DetectionResult:
        """Detect content type using multiple heuristics."""
        logger.debug(f"Detecting content type for '{disc_name}' with {len(titles)} titles")
        
        # 1. Check manual override first (highest priority)
        override_result = self._check_manual_override(disc_name)
        if override_result:
            return override_result
        
        # 2. Check known TV shows database
        known_tv_result = self._check_known_tv_shows(disc_name)
        if known_tv_result:
            return known_tv_result
        
        # Filter out short/extra content
        main_titles = self._filter_main_content(titles)
        
        if not main_titles:
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="No main content titles found"
            )
        
        # 3. Check multi-disc pattern (Disc 1, Disc 2, etc.)
        multidisc_result = self._check_multidisc_pattern(disc_name)
        if multidisc_result:
            return multidisc_result
        
        # Run remaining detection methods
        name_result = self._detect_by_name(disc_name)
        duration_result = self._detect_by_duration_pattern(main_titles)
        size_result = self._detect_by_size_distribution(main_titles)
        count_result = self._detect_by_title_count(main_titles)
        cluster_result = self._detect_by_clustering(main_titles)
        
        # Combine results with weighted voting
        return self._combine_results(
            [name_result, duration_result, size_result, count_result, cluster_result],
            disc_name,
            main_titles
        )
    
    def _check_manual_override(self, disc_name: str) -> Optional[DetectionResult]:
        """Check if there's a manual override in config."""
        if not self.config or not hasattr(self.config, 'detection'):
            return None
            
        forced_types = getattr(self.config.detection, 'forced_types', {})
        if not forced_types:
            return None
        
        # Check exact match
        if disc_name in forced_types:
            forced_type = forced_types[disc_name]
            content_type = ContentType.TV_SHOW if forced_type == "tvshow" else ContentType.MOVIE
            return DetectionResult(
                content_type=content_type,
                confidence="high",
                reason=f"Manual override in config: forced as {forced_type}",
                suggested_name=self._clean_name(disc_name)
            )
        
        # Check case-insensitive match
        disc_lower = disc_name.lower()
        for name, forced_type in forced_types.items():
            if name.lower() == disc_lower:
                content_type = ContentType.TV_SHOW if forced_type == "tvshow" else ContentType.MOVIE
                return DetectionResult(
                    content_type=content_type,
                    confidence="high",
                    reason=f"Manual override in config: forced as {forced_type}",
                    suggested_name=self._clean_name(disc_name)
                )
        
        return None
    
    def _check_known_tv_shows(self, disc_name: str) -> Optional[DetectionResult]:
        """Check if disc name matches known TV shows with movie-length episodes."""
        disc_lower = disc_name.lower()
        
        for known_show in KNOWN_TV_SHOWS:
            if known_show in disc_lower:
                return DetectionResult(
                    content_type=ContentType.TV_SHOW,
                    confidence="high",
                    reason=f"Detected as TV show: '{known_show}' is in known TV shows database",
                    suggested_name=self._clean_name(disc_name)
                )
        
        return None
    
    def _check_multidisc_pattern(self, disc_name: str) -> Optional[DetectionResult]:
        """Check if disc name suggests multi-disc TV series."""
        # Look for patterns like "Disc 1", "Disc 2", "Part 1", "Volume 1"
        multidisc_pattern = re.search(
            r'(?:\s*[-:]?\s*(?:disc|part|volume|vol)\s*\d+)$', 
            disc_name, 
            re.IGNORECASE
        )
        
        if multidisc_pattern:
            return DetectionResult(
                content_type=ContentType.TV_SHOW,
                confidence="high",
                reason=f"Multi-disc pattern detected: '{multidisc_pattern.group(0)}'",
                suggested_name=self._clean_name(disc_name)
            )
        
        return None
    
    def _detect_by_title_count(self, titles: list[TitleInfo]) -> DetectionResult:
        """Detect based on number of titles and their durations."""
        if len(titles) < 2:
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="Insufficient titles for count analysis"
            )
        
        durations = [t.duration // 60 for t in titles]  # in minutes
        
        # TV series pattern: 2-8 titles, each 45-120 minutes
        # (typical for British series with movie-length episodes)
        if 2 <= len(titles) <= 12:
            # Check if all durations are in TV episode range (including movie-length)
            tv_duration_count = sum(1 for d in durations if 40 <= d <= 130)
            
            if tv_duration_count >= len(titles) * 0.8:  # 80% match
                avg_duration = sum(durations) / len(durations)
                return DetectionResult(
                    content_type=ContentType.TV_SHOW,
                    confidence="high",
                    reason=f"{len(titles)} titles with TV episode durations (avg {int(avg_duration)} min each)"
                )
        
        # Movie pattern: 1-2 main titles, one significantly longer
        if len(titles) <= 3:
            max_duration = max(durations)
            if max_duration >= 80:  # At least 80 minutes
                return DetectionResult(
                    content_type=ContentType.MOVIE,
                    confidence="medium",
                    reason=f"{len(titles)} titles, longest is {max_duration} min"
                )
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="Title count analysis inconclusive"
        )
    
    def _filter_main_content(self, titles: list[TitleInfo]) -> list[TitleInfo]:
        """Filter out extras, trailers, and short content."""
        min_duration = 10 * 60  # 10 minutes in seconds
        return [t for t in titles if t.duration >= min_duration]
    
    def _detect_by_name(self, disc_name: str) -> DetectionResult:
        """Detect based on disc name patterns."""
        name_lower = disc_name.lower()
        
        # TV indicators
        tv_indicators = [
            r'season\s*\d+', r's\d{1,2}', r'temporada\s*\d+',
            r'disc\s*\d+', r'volume\s*\d+', r'part\s*\d+',
            r'episodes?', r'chapters?', r'complete\s+series',
            r'the\s+complete', r'box\s+set', r'tv\s+series',
        ]
        
        for pattern in tv_indicators:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return DetectionResult(
                    content_type=ContentType.TV_SHOW,
                    confidence="high",
                    reason=f"Disc name matches TV pattern"
                )
        
        # Movie indicators
        movie_indicators = [
            r'\(\d{4}\)', r'\d{4}$', r'criterion',
            r'director\'s\s+cut', r'extended\s+cut',
        ]
        
        for pattern in movie_indicators:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return DetectionResult(
                    content_type=ContentType.MOVIE,
                    confidence="high",
                    reason=f"Disc name matches movie pattern"
                )
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="No clear name indicators"
        )
    
    def _detect_by_duration_pattern(self, titles: list[TitleInfo]) -> DetectionResult:
        """Detect based on title duration patterns."""
        if len(titles) < 2:
            if titles and titles[0].duration >= self.min_movie_duration * 60:
                duration_min = titles[0].duration // 60
                return DetectionResult(
                    content_type=ContentType.MOVIE,
                    confidence="medium",
                    reason=f"Single title with movie-length duration ({duration_min} min)"
                )
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="Single short title"
            )
        
        durations = [t.duration // 60 for t in titles]
        
        if len(durations) >= 2:
            variance = statistics.variance(durations)
            mean_duration = statistics.mean(durations)
            
            # Low variance = similar lengths = likely TV
            if variance < 100:
                # Check if TV episode patterns
                for pattern_name, (min_d, max_d) in {
                    "sitcom": (18, 26),
                    "drama": (38, 52),
                    "premium": (50, 65),
                    "movie-length": (60, 130),
                }.items():
                    if all(min_d <= d <= max_d for d in durations):
                        return DetectionResult(
                            content_type=ContentType.TV_SHOW,
                            confidence="high",
                            reason=f"All titles have similar {pattern_name} durations"
                        )
                
                if mean_duration >= self.min_movie_duration:
                    return DetectionResult(
                        content_type=ContentType.MOVIE,
                        confidence="medium",
                        reason=f"Similar durations around {int(mean_duration)} min"
                    )
            else:
                # High variance
                max_duration = max(durations)
                total_duration = sum(durations)
                
                if total_duration == 0:
                    return DetectionResult(
                        content_type=ContentType.UNKNOWN,
                        confidence="low",
                        reason="Cannot analyze: zero total duration"
                    )
                
                if max_duration / total_duration > 0.7:
                    return DetectionResult(
                        content_type=ContentType.MOVIE,
                        confidence="high",
                        reason=f"One dominant title ({max_duration} min)"
                    )
                else:
                    return DetectionResult(
                        content_type=ContentType.TV_SHOW,
                        confidence="medium",
                        reason=f"Multiple titles with varying durations"
                    )
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="Duration analysis inconclusive"
        )
    
    def _detect_by_size_distribution(self, titles: list[TitleInfo]) -> DetectionResult:
        """Detect based on file size distribution."""
        if len(titles) < 2:
            if titles and titles[0].size_bytes > 10 * 1024**3:
                return DetectionResult(
                    content_type=ContentType.MOVIE,
                    confidence="high",
                    reason="Single large title (>10GB)"
                )
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="Insufficient size data"
            )
        
        sizes = [t.size_bytes / (1024**3) for t in titles]
        
        if len(sizes) >= 2:
            total_size = sum(sizes)
            max_size = max(sizes)
            mean_size = statistics.mean(sizes)
            
            if total_size == 0:
                return DetectionResult(
                    content_type=ContentType.UNKNOWN,
                    confidence="low",
                    reason="Cannot analyze: zero total size"
                )
            
            if max_size / total_size > 0.8:
                return DetectionResult(
                    content_type=ContentType.MOVIE,
                    confidence="high",
                    reason=f"One dominant file ({max_size:.1f}GB)"
                )
            
            if len(sizes) >= 2 and mean_size > 0:
                try:
                    variance = statistics.variance(sizes)
                    if variance / (mean_size ** 2) < 0.3:
                        return DetectionResult(
                            content_type=ContentType.TV_SHOW,
                            confidence="high",
                            reason=f"Files of similar size (~{mean_size:.1f}GB each)"
                        )
                except statistics.StatisticsError:
                    pass
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="Size distribution inconclusive"
        )
    
    def _detect_by_clustering(self, titles: list[TitleInfo]) -> DetectionResult:
        """Use clustering to detect episode patterns."""
        if len(titles) < 3:
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="Need at least 3 titles for clustering"
            )
        
        durations = [t.duration // 60 for t in titles]
        clusters = []
        sorted_durations = sorted(durations)
        current_cluster = [sorted_durations[0]]
        
        for d in sorted_durations[1:]:
            if abs(d - statistics.mean(current_cluster)) <= 5:
                current_cluster.append(d)
            else:
                clusters.append(current_cluster)
                current_cluster = [d]
        clusters.append(current_cluster)
        
        largest_cluster = max(clusters, key=len)
        if len(largest_cluster) >= len(titles) * 0.7 and len(largest_cluster) >= 2:
            mean_dur = statistics.mean(largest_cluster)
            return DetectionResult(
                content_type=ContentType.TV_SHOW,
                confidence="high",
                reason=f"{len(largest_cluster)} titles cluster around {int(mean_dur)} min"
            )
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="Clustering inconclusive"
        )
    
    def _combine_results(self, results: list[DetectionResult], disc_name: str,
                        titles: list[TitleInfo]) -> DetectionResult:
        """Combine multiple detection results with weighted voting."""
        
        tv_votes = 0
        movie_votes = 0
        reasons = []
        
        for r in results:
            weight = 1.0
            if r.confidence == "high":
                weight = 2.0
            elif r.confidence == "medium":
                weight = 1.0
            else:
                weight = 0.5
            
            if r.content_type == ContentType.TV_SHOW:
                tv_votes += weight
            elif r.content_type == ContentType.MOVIE:
                movie_votes += weight
            
            if r.reason and r.confidence in ("high", "medium"):
                reasons.append(r.reason)
        
        # Decide
        if tv_votes > movie_votes:
            confidence = "high" if tv_votes >= 3 else "medium"
            return DetectionResult(
                content_type=ContentType.TV_SHOW,
                confidence=confidence,
                reason=f"TV Show: {'; '.join(reasons[:2])}",
                suggested_name=self._clean_name(disc_name)
            )
        elif movie_votes > tv_votes:
            confidence = "high" if movie_votes >= 3 else "medium"
            return DetectionResult(
                content_type=ContentType.MOVIE,
                confidence=confidence,
                reason=f"Movie: {'; '.join(reasons[:2])}",
                suggested_name=self._clean_name(disc_name)
            )
        else:
            if titles:
                longest = max(titles, key=lambda t: t.duration)
                if longest.duration >= 90 * 60:
                    return DetectionResult(
                        content_type=ContentType.MOVIE,
                        confidence="medium",
                        reason=f"Ambiguous, but longest is {longest.duration//60} min",
                        suggested_name=self._clean_name(disc_name)
                    )
            
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="Could not determine content type",
                suggested_name=self._clean_name(disc_name)
            )
    
    def _clean_name(self, name: str) -> str:
        """Clean disc name by removing season/episode indicators."""
        cleaned = re.sub(r'\s*[-:]?\s*(?:season|temporada)\s*\d+.*$', '', name, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+s\d+.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*[-:]?\s*disc\s*\d+.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*[-:]?\s*(?:part|volume|vol)\s*\d+.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*\(\d{4}\)\s*$', '', cleaned)
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()


def detect_content_type(titles: list[TitleInfo], disc_name: str, config: Config = None,
                       min_episode_duration: int = 15, max_episode_duration: int = 70,
                       min_movie_duration: int = 60) -> tuple[ContentType, str]:
    """Convenience function for content type detection."""
    detector = SmartContentDetector(
        config=config,
        min_episode_duration=min_episode_duration,
        max_episode_duration=max_episode_duration,
        min_movie_duration=min_movie_duration
    )
    
    result = detector.detect(titles, disc_name)
    
    logger.info(f"Detected '{disc_name}': {result.content_type.value} "
                f"(confidence: {result.confidence}) - {result.reason}")
    
    return result.content_type, result.confidence
