"""
AnalyticsRunRepository - Analytics pipeline execution data access.

Handles execution tracking, performance monitoring, result aggregation,
and pipeline orchestration queries.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.orm import Session

from database.models import AnalyticsRuns, Places
from .base import BaseRepository


class AnalyticsRunRepository(BaseRepository[AnalyticsRuns]):
    """Repository for AnalyticsRuns entities.

    Specializes in pipeline execution tracking and performance monitoring.
    """

    def __init__(self, session: Session):
        """Initialize AnalyticsRunRepository.

        Args:
            session: SQLAlchemy session
        """
        super().__init__(session, AnalyticsRuns)

    # =====================================================================
    # Execution Tracking
    # =====================================================================

    def find_by_place(self, place_id: str, limit: int = 50) -> List[AnalyticsRuns]:
        """Get all analytics runs for a place.

        Args:
            place_id: Place identifier
            limit: Maximum results

        Returns:
            Analytics runs for place
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.place_id == place_id)
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_active_runs(self) -> List[AnalyticsRuns]:
        """Get currently active/running executions.

        Returns:
            Active runs
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.execution_status == "RUNNING")
            .order_by(self.entity_class.execution_date.desc())
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_status(self, status: str, limit: int = 100) -> List[AnalyticsRuns]:
        """Find runs by execution status.

        Args:
            status: Execution status (PENDING, RUNNING, COMPLETED, FAILED)
            limit: Maximum results

        Returns:
            Runs with status
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.execution_status == status)
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_time_range(
        self, start_date: datetime, end_date: datetime, limit: int = 200
    ) -> List[AnalyticsRuns]:
        """Find runs within time range.

        Args:
            start_date: Start datetime
            end_date: End datetime
            limit: Maximum results

        Returns:
            Runs in range
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.execution_date >= start_date,
                    self.entity_class.execution_date <= end_date,
                )
            )
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    # =====================================================================
    # Performance Analysis
    # =====================================================================

    def find_slow_executions(self, threshold_seconds: int = 60, limit: int = 50) -> List[AnalyticsRuns]:
        """Find executions exceeding time threshold.

        Args:
            threshold_seconds: Maximum acceptable execution time
            limit: Maximum results

        Returns:
            Slow executions
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.execution_time_seconds > threshold_seconds)
            .order_by(self.entity_class.execution_time_seconds.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_fast_executions(self, threshold_seconds: int = 5, limit: int = 50) -> List[AnalyticsRuns]:
        """Find quick executions (under threshold).

        Args:
            threshold_seconds: Maximum time for "fast"
            limit: Maximum results

        Returns:
            Fast executions
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.execution_time_seconds <= threshold_seconds)
            .order_by(self.entity_class.execution_time_seconds.asc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_execution_performance(self, place_id: Optional[str] = None) -> Dict[str, Any]:
        """Get execution performance statistics.

        Args:
            place_id: Optional place filter

        Returns:
            Performance metrics
        """
        stmt = select(self.entity_class)

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        runs = self.session.execute(stmt).scalars().all()

        if not runs:
            return {
                "total_runs": 0,
                "avg_execution_time": 0,
                "max_execution_time": 0,
                "min_execution_time": 0,
            }

        exec_times = [r.execution_time_seconds for r in runs if r.execution_time_seconds]
        return {
            "total_runs": len(runs),
            "avg_execution_time": sum(exec_times) / len(exec_times) if exec_times else 0,
            "max_execution_time": max(exec_times) if exec_times else 0,
            "min_execution_time": min(exec_times) if exec_times else 0,
        }

    # =====================================================================
    # Result Aggregation
    # =====================================================================

    def find_high_result_runs(self, min_results: int = 100, limit: int = 50) -> List[AnalyticsRuns]:
        """Find runs with high result counts.

        Args:
            min_results: Minimum result threshold
            limit: Maximum results

        Returns:
            High result runs
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.results_generated >= min_results)
            .order_by(self.entity_class.results_generated.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_result_statistics(self, place_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics on results generated.

        Args:
            place_id: Optional place filter

        Returns:
            Result statistics
        """
        stmt = select(
            func.count(self.entity_class.id).label("total_runs"),
            func.sum(self.entity_class.results_generated).label("total_results"),
            func.avg(self.entity_class.results_generated).label("avg_results"),
            func.max(self.entity_class.results_generated).label("max_results"),
        )

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        result = self.session.execute(stmt).first()

        return {
            "total_runs": result[0] or 0,
            "total_results": result[1] or 0,
            "avg_results_per_run": result[2] or 0,
            "max_results": result[3] or 0,
        }

    # =====================================================================
    # Error & Failure Analysis
    # =====================================================================

    def find_failed_runs(self, limit: int = 50) -> List[AnalyticsRuns]:
        """Get failed executions.

        Returns:
            Failed runs
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.execution_status == "FAILED")
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_failed_by_place(self, place_id: str, limit: int = 50) -> List[AnalyticsRuns]:
        """Get failed runs for specific place.

        Args:
            place_id: Place identifier
            limit: Maximum results

        Returns:
            Failed runs for place
        """
        stmt = (
            select(self.entity_class)
            .where(
                and_(
                    self.entity_class.place_id == place_id,
                    self.entity_class.execution_status == "FAILED",
                )
            )
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_failure_rate(self, place_id: Optional[str] = None) -> float:
        """Calculate failure rate percentage.

        Args:
            place_id: Optional place filter

        Returns:
            Failure rate (0-100)
        """
        stmt = select(self.entity_class)

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        total = self.session.execute(select(func.count(self.entity_class.id)).select_from(
            self.entity_class
        )).scalar() or 0

        if total == 0:
            return 0.0

        failed_stmt = select(func.count(self.entity_class.id)).where(
            self.entity_class.execution_status == "FAILED"
        )

        if place_id:
            failed_stmt = failed_stmt.where(self.entity_class.place_id == place_id)

        failed = self.session.execute(failed_stmt).scalar() or 0

        return (failed / total * 100) if total > 0 else 0.0

    # =====================================================================
    # Pipeline History & Trends
    # =====================================================================

    def get_recent_runs(self, days: int = 7, limit: int = 50) -> List[AnalyticsRuns]:
        """Get recent analytics runs.

        Args:
            days: Look back period
            limit: Maximum results

        Returns:
            Recent runs
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.execution_date >= cutoff)
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_execution_trend(self, days: int = 30) -> Dict[str, int]:
        """Get execution count trend by day.

        Args:
            days: Look back period

        Returns:
            Daily execution counts
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(
            func.date(self.entity_class.execution_date).label("date"),
            func.count(self.entity_class.id).label("count"),
        ).where(
            self.entity_class.execution_date >= cutoff
        ).group_by(
            func.date(self.entity_class.execution_date)
        ).order_by(
            func.date(self.entity_class.execution_date)
        )

        results = self.session.execute(stmt).all()
        return {str(date): count for date, count in results}

    def get_status_distribution(self, place_id: Optional[str] = None) -> Dict[str, int]:
        """Get distribution of execution statuses.

        Args:
            place_id: Optional place filter

        Returns:
            Count by status
        """
        stmt = select(
            self.entity_class.execution_status,
            func.count(self.entity_class.id).label("count"),
        ).group_by(self.entity_class.execution_status)

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        results = self.session.execute(stmt).all()
        return {status: count for status, count in results if status}

    # =====================================================================
    # Configuration & Batch Operations
    # =====================================================================

    def find_by_config_version(self, config_version: str, limit: int = 100) -> List[AnalyticsRuns]:
        """Find runs using specific config version.

        Args:
            config_version: Configuration version identifier
            limit: Maximum results

        Returns:
            Runs with config version
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.config_version == config_version)
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def find_by_pipeline_version(self, pipeline_version: str, limit: int = 100) -> List[AnalyticsRuns]:
        """Find runs using specific pipeline version.

        Args:
            pipeline_version: Pipeline version identifier
            limit: Maximum results

        Returns:
            Runs with pipeline version
        """
        stmt = (
            select(self.entity_class)
            .where(self.entity_class.pipeline_version == pipeline_version)
            .order_by(self.entity_class.execution_date.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def compare_configurations(
        self, config_version1: str, config_version2: str
    ) -> Dict[str, Any]:
        """Compare performance of two config versions.

        Args:
            config_version1: First config version
            config_version2: Second config version

        Returns:
            Comparison metrics
        """
        def get_stats(config_version: str) -> Dict[str, Any]:
            stmt = select(self.entity_class).where(
                self.entity_class.config_version == config_version
            )
            runs = self.session.execute(stmt).scalars().all()
            if not runs:
                return {}
            
            times = [r.execution_time_seconds for r in runs if r.execution_time_seconds]
            results = [r.results_generated for r in runs if r.results_generated]
            
            return {
                "count": len(runs),
                "avg_time": sum(times) / len(times) if times else 0,
                "total_results": sum(results) if results else 0,
            }

        stats1 = get_stats(config_version1)
        stats2 = get_stats(config_version2)

        return {
            "config1": config_version1,
            "config1_stats": stats1,
            "config2": config_version2,
            "config2_stats": stats2,
            "time_improvement": (
                ((stats1.get("avg_time", 0) - stats2.get("avg_time", 0)) / stats1.get("avg_time", 1) * 100)
                if stats1.get("avg_time", 0) > 0
                else 0
            ),
        }

    # =====================================================================
    # Orchestration Queries
    # =====================================================================

    def get_next_pending_run(self, place_id: Optional[str] = None) -> Optional[AnalyticsRuns]:
        """Get next pending run for scheduling.

        Args:
            place_id: Optional place filter

        Returns:
            Next pending run or None
        """
        stmt = select(self.entity_class).where(
            self.entity_class.execution_status == "PENDING"
        ).order_by(self.entity_class.created_at.asc()).limit(1)

        if place_id:
            stmt = stmt.where(self.entity_class.place_id == place_id)

        return self.session.execute(stmt).scalar()

    def mark_as_running(self, run_id: str) -> bool:
        """Mark run as currently executing.

        Args:
            run_id: Run identifier

        Returns:
            Success flag
        """
        run = self.get_by_id(run_id)
        if run:
            run.execution_status = "RUNNING"
            run.execution_date = datetime.utcnow()
            self.session.flush()
            return True
        return False

    def mark_as_completed(
        self, run_id: str, execution_time: int, results_count: int
    ) -> bool:
        """Mark run as completed.

        Args:
            run_id: Run identifier
            execution_time: Seconds to complete
            results_count: Number of results generated

        Returns:
            Success flag
        """
        run = self.get_by_id(run_id)
        if run:
            run.execution_status = "COMPLETED"
            run.execution_time_seconds = execution_time
            run.results_generated = results_count
            run.completed_at = datetime.utcnow()
            self.session.flush()
            return True
        return False

    def mark_as_failed(self, run_id: str, error_message: str) -> bool:
        """Mark run as failed.

        Args:
            run_id: Run identifier
            error_message: Error details

        Returns:
            Success flag
        """
        run = self.get_by_id(run_id)
        if run:
            run.execution_status = "FAILED"
            run.error_message = error_message
            run.completed_at = datetime.utcnow()
            self.session.flush()
            return True
        return False

    def get_execution_summary(self, place_id: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive execution summary.

        Args:
            place_id: Optional place filter

        Returns:
            Summary of all key metrics
        """
        base_stats = self.get_execution_performance(place_id)
        result_stats = self.get_result_statistics(place_id)
        status_dist = self.get_status_distribution(place_id)
        failure_rate = self.get_failure_rate(place_id)

        return {
            "execution_metrics": base_stats,
            "result_metrics": result_stats,
            "status_distribution": status_dist,
            "failure_rate_percent": failure_rate,
            "timestamp": datetime.utcnow().isoformat(),
        }
