"""Advanced content type detection for Blu-ray/DVD discs."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from makemkv_auto.logger import get_logger

logger = get_logger(__name__)


class ContentType(Enum):
    """Content type enumeration."""
    MOVIE = "movie"
    TV_SHOW = "tvshow"
    UNKNOWN = "unknown"


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
    
    Key insights:
    - TV episodes cluster around similar durations (20-25min or 40-50min)
    - Movies have one dominant title with much larger size
    - Blu-rays may split movies into chapters, but duration pattern differs
    """
    
    # Typical episode durations in minutes
    TV_EPISODE_PATTERNS = {
        "sitcom": (18, 26),      # 18-26 minutes
        "drama": (38, 52),       # 38-52 minutes
        "animated": (20, 24),    # 20-24 minutes
        "premium": (50, 65),     # 50-65 minutes (HBO, etc.)
    }
    
    # TV indicators in disc names (case-insensitive)
    TV_NAME_INDICATORS = [
        r'season\s*\d+',           # Season 1, Season 2, etc.
        r's\d{1,2}',               # S1, S2, S01, S12
        r'temporada\s*\d+',        # Temporada 1 (Spanish)
        r'disc\s*\d+',              # Disc 1, Disc 2
        r'volume\s*\d+',           # Volume 1
        r'part\s*\d+',             # Part 1
        r'episodes?',               # Episode, Episodes
        r'chapters?',               # Chapters (TV releases)
        r'complete\s+series',       # Complete Series
        r'the\s+complete',          # The Complete
        r'collector\'s\s+set',      # Collector's Set
        r'box\s+set',               # Box Set
        r'tv\s+series',             # TV Series
    ]
    
    # Movie indicators in disc names
    MOVIE_NAME_INDICATORS = [
        r'\(\d{4}\)',              # Year in parentheses: (2023)
        r'\d{4}$',                  # Year at end: Movie Name 2023
        r'\[remastered\]',         # [Remastered]
        r'\[collector',            # [Collector's Edition]
        r'4k\s+remaster',          # 4K Remaster
        r'criterion',               # Criterion Collection
        r'director\'s\s+cut',      # Director's Cut
        r'extended\s+cut',         # Extended Cut
        r'theatrical\s+cut',       # Theatrical Cut
        r'ultimate\s+edition',     # Ultimate Edition
    ]
    
    def __init__(self, min_episode_duration: int = 15, max_episode_duration: int = 70,
                 min_movie_duration: int = 60) -> None:
        self.min_episode_duration = min_episode_duration
        self.max_episode_duration = max_episode_duration
        self.min_movie_duration = min_movie_duration
    
    def detect(self, titles: list[TitleInfo], disc_name: str) -> DetectionResult:
        """
        Detect content type using multiple heuristics.
        
        Returns DetectionResult with type, confidence, and explanation.
        """
        logger.debug(f"Detecting content type for '{disc_name}' with {len(titles)} titles")
        
        # Filter out short/extra content
        main_titles = self._filter_main_content(titles)
        
        if not main_titles:
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="No main content titles found"
            )
        
        # Run multiple detection methods
        name_result = self._detect_by_name(disc_name)
        duration_result = self._detect_by_duration_pattern(main_titles)
        size_result = self._detect_by_size_distribution(main_titles)
        cluster_result = self._detect_by_clustering(main_titles)
        
        # Combine results with weighted voting
        return self._combine_results(
            [name_result, duration_result, size_result, cluster_result],
            disc_name,
            main_titles
        )
    
    def _filter_main_content(self, titles: list[TitleInfo]) -> list[TitleInfo]:
        """Filter out extras, trailers, and short content."""
        # Keep titles longer than 10 minutes
        min_duration = 10 * 60  # 10 minutes in seconds
        return [t for t in titles if t.duration >= min_duration]
    
    def _detect_by_name(self, disc_name: str) -> DetectionResult:
        """Detect based on disc name patterns."""
        name_lower = disc_name.lower()
        
        # Check for TV indicators
        for pattern in self.TV_NAME_INDICATORS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                # Extract season number if present
                season_match = re.search(r'(?:season|s|temporada)\s*(\d+)', name_lower, re.IGNORECASE)
                if season_match:
                    reason = f"Disc name contains season indicator (Season {season_match.group(1)})"
                else:
                    reason = f"Disc name matches TV pattern: '{pattern}'"
                
                return DetectionResult(
                    content_type=ContentType.TV_SHOW,
                    confidence="high",
                    reason=reason
                )
        
        # Check for movie indicators
        for pattern in self.MOVIE_NAME_INDICATORS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return DetectionResult(
                    content_type=ContentType.MOVIE,
                    confidence="high",
                    reason=f"Disc name matches movie pattern: '{pattern}'"
                )
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="No clear name indicators found"
        )
    
    def _detect_by_duration_pattern(self, titles: list[TitleInfo]) -> DetectionResult:
        """Detect based on title duration patterns."""
        if len(titles) < 2:
            # Single title - likely a movie if long enough
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
        
        # Multiple titles - analyze duration variance
        durations = [t.duration // 60 for t in titles]  # Convert to minutes
        
        if len(durations) >= 2:
            variance = statistics.variance(durations)
            mean_duration = statistics.mean(durations)
            
            # TV episodes have low variance (similar lengths)
            # Movies split into chapters might have different pattern
            if variance < 100:  # Low variance threshold
                # Check if durations match typical episode patterns
                for pattern_name, (min_d, max_d) in self.TV_EPISODE_PATTERNS.items():
                    if all(min_d <= d <= max_d for d in durations):
                        return DetectionResult(
                            content_type=ContentType.TV_SHOW,
                            confidence="high",
                            reason=f"All {len(titles)} titles have similar {pattern_name} episode durations "
                                   f"({min_d}-{max_d} min each)"
                        )
                
                # Similar durations but not matching known episode patterns
                if mean_duration >= self.min_movie_duration:
                    return DetectionResult(
                        content_type=ContentType.MOVIE,
                        confidence="medium",
                        reason=f"{len(titles)} titles with similar durations around {int(mean_duration)} min "
                               f"(possible movie chapters)"
                    )
            else:
                # High variance - likely a mix or movie with extras
                max_duration = max(durations)
                total_duration = sum(durations)
                
                # If one title dominates (>70% of total duration), it's probably a movie
                if max_duration / total_duration > 0.7:
                    return DetectionResult(
                        content_type=ContentType.MOVIE,
                        confidence="high",
                        reason=f"One dominant title ({max_duration} min, {max_duration/total_duration*100:.0f}% of total)"
                    )
                else:
                    # Multiple similar-sized titles with variance - could be TV
                    return DetectionResult(
                        content_type=ContentType.TV_SHOW,
                        confidence="medium",
                        reason=f"{len(titles)} titles with varying durations, suggesting episodes"
                    )
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="Duration analysis inconclusive"
        )
    
    def _detect_by_size_distribution(self, titles: list[TitleInfo]) -> DetectionResult:
        """Detect based on file size distribution."""
        if len(titles) < 2:
            if titles and titles[0].size_bytes > 10 * 1024**3:  # >10GB
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
        
        sizes = [t.size_bytes / (1024**3) for t in titles]  # Convert to GB
        
        if len(sizes) >= 2:
            total_size = sum(sizes)
            max_size = max(sizes)
            mean_size = statistics.mean(sizes)
            
            # If one file dominates (>80%), it's likely a movie
            if max_size / total_size > 0.8:
                return DetectionResult(
                    content_type=ContentType.MOVIE,
                    confidence="high",
                    reason=f"One dominant file ({max_size:.1f}GB, {max_size/total_size*100:.0f}% of total size)"
                )
            
            # If files are similar size (<30% variance), likely TV episodes
            if len(sizes) >= 2:
                try:
                    variance = statistics.variance(sizes)
                    if variance / (mean_size ** 2) < 0.3:  # Coefficient of variation < 30%
                        return DetectionResult(
                            content_type=ContentType.TV_SHOW,
                            confidence="high",
                            reason=f"{len(titles)} files of similar size (~{mean_size:.1f}GB each)"
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
        
        # Simple clustering: group by similar durations (within 5 min)
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
        
        # If we have one large cluster with most titles, likely TV show
        largest_cluster = max(clusters, key=len)
        if len(largest_cluster) >= len(titles) * 0.7 and len(largest_cluster) >= 2:
            mean_dur = statistics.mean(largest_cluster)
            return DetectionResult(
                content_type=ContentType.TV_SHOW,
                confidence="high",
                reason=f"{len(largest_cluster)} of {len(titles)} titles cluster around {int(mean_dur)} min"
            )
        
        return DetectionResult(
            content_type=ContentType.UNKNOWN,
            confidence="low",
            reason="Clustering results inconclusive"
        )
    
    def _combine_results(self, results: list[DetectionResult], disc_name: str,
                        titles: list[TitleInfo]) -> DetectionResult:
        """Combine multiple detection results with weighted voting."""
        
        # Weight by confidence
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
        
        # Decide based on votes
        if tv_votes > movie_votes:
            confidence = "high" if tv_votes >= 3 else "medium"
            return DetectionResult(
                content_type=ContentType.TV_SHOW,
                confidence=confidence,
                reason=f"TV Show detected: {'; '.join(reasons[:2])}",
                suggested_name=self._clean_name(disc_name)
            )
        elif movie_votes > tv_votes:
            confidence = "high" if movie_votes >= 3 else "medium"
            return DetectionResult(
                content_type=ContentType.MOVIE,
                confidence=confidence,
                reason=f"Movie detected: {'; '.join(reasons[:2])}",
                suggested_name=self._clean_name(disc_name)
            )
        else:
            # Tie-breaker: duration of longest title
            if titles:
                longest = max(titles, key=lambda t: t.duration)
                if longest.duration >= 90 * 60:  # 90+ minutes
                    return DetectionResult(
                        content_type=ContentType.MOVIE,
                        confidence="medium",
                        reason=f"Ambiguous pattern, but longest title is {longest.duration//60} min (movie-length)",
                        suggested_name=self._clean_name(disc_name)
                    )
            
            return DetectionResult(
                content_type=ContentType.UNKNOWN,
                confidence="low",
                reason="Could not determine content type from available data",
                suggested_name=self._clean_name(disc_name)
            )
    
    def _clean_name(self, name: str) -> str:
        """Clean disc name by removing season/episode indicators for folder naming."""
        # Remove season indicators
        cleaned = re.sub(r'\s*[-:]?\s*(?:season|temporada)\s*\d+.*$', '', name, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+s\d+.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*[-:]?\s*disc\s*\d+.*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*\(\d{4}\)\s*$', '', cleaned)  # Remove year
        
        # Clean up whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned.strip()


def detect_content_type(titles: list[TitleInfo], disc_name: str,
                       min_episode_duration: int = 15,
                       max_episode_duration: int = 70,
                       min_movie_duration: int = 60) -> tuple[ContentType, str]:
    """
    Convenience function for content type detection.
    
    Returns (content_type, confidence) for backward compatibility.
    """
    detector = SmartContentDetector(
        min_episode_duration=min_episode_duration,
        max_episode_duration=max_episode_duration,
        min_movie_duration=min_movie_duration
    )
    
    result = detector.detect(titles, disc_name)
    
    logger.info(f"Content detection for '{disc_name}': {result.content_type.value} "
                f"(confidence: {result.confidence}) - {result.reason}")
    
    return result.content_type, result.confidence
