"""
Chart Generator - Handles all chart generation for summary reports
Separates matplotlib/visualization logic from views
"""

import io
import base64
import os
import inspect
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")  # Use non-GUI backend

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.font_manager import FontProperties


class ChartGenerator:
    """Generates charts for summary dashboard and PDF reports"""

    MONTH_NAMES = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    @staticmethod
    def _get_thai_font() -> Optional[FontProperties]:
        """Get Thai font properties for charts"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            font_dir = os.path.join(base_dir, "..", "web", "static", "fonts")
            font_dir = os.path.abspath(font_dir)
            thai_font_path = os.path.join(font_dir, "Sarabun-Regular.ttf")

            if os.path.exists(thai_font_path):
                return FontProperties(fname=thai_font_path)
        except Exception:
            pass

        return None

    @classmethod
    def generate_bar_chart(
        cls,
        current_data: Dict[str, float],
        previous_data: Optional[Dict[str, float]] = None,
        selected_year: Optional[int] = None,
    ) -> str:
        """
        Generate a grouped bar chart comparing current and previous year monthly emissions

        Args:
            current_data: Dict mapping month names to emission values
            previous_data: Optional dict for previous year data
            selected_year: Year for labeling

        Returns:
            Base64 encoded PNG image
        """
        sns.set_style(
            "whitegrid",
            {
                "axes.facecolor": "#EAEAF2",
                "grid.color": "white",
                "axes.edgecolor": "#EAEAF2",
            },
        )

        month_labels = [m[:3] for m in cls.MONTH_NAMES]
        current_values = [current_data.get(m, 0) for m in cls.MONTH_NAMES]
        previous_values = (
            [previous_data.get(m, 0) for m in cls.MONTH_NAMES]
            if previous_data
            else [0] * 12
        )

        fig, ax = plt.subplots(figsize=(6, 3))

        # Add zebra stripes to background
        y_ticks = ax.get_yticks()
        for i in range(len(y_ticks) - 1):
            if i % 2 == 0:
                ax.axhspan(
                    y_ticks[i], y_ticks[i + 1], facecolor="#f0f0f0", alpha=0.3, zorder=1
                )

        bar_width = 0.35
        x = range(len(month_labels))

        # Get year from caller context if not provided
        if not selected_year:
            from datetime import datetime

            selected_year = datetime.now().year

        # Create bars
        ax.bar(
            [i - bar_width / 2 for i in x],
            previous_values,
            width=bar_width,
            color="#4F46E5",
            label=f"{int(selected_year) - 1}",
            zorder=2,
        )
        ax.bar(
            [i + bar_width / 2 for i in x],
            current_values,
            width=bar_width,
            color="#10B981",
            label=f"{int(selected_year)}",
            zorder=2,
        )

        # Labels and formatting
        ax.set_ylabel("Emissions (tCO$_2$e)")
        ax.set_xlabel("Month")
        ax.set_title("Emissions by Month")
        ax.set_xticks(x)
        ax.set_xticklabels(month_labels, rotation=30, ha="right")
        ax.grid(True, axis="y", linestyle="--", alpha=0.5, zorder=3)

        # Legend with Thai font
        font_prop = cls._get_thai_font()
        ax.legend(
            title="ปี ค.ศ.",
            prop=font_prop,
            title_fontproperties=font_prop,
            loc="upper right",
            bbox_to_anchor=(1.12, 1),
        )

        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode("utf-8")

    @classmethod
    def generate_donut_chart(cls, category_data: Dict[str, float]) -> str:
        """
        Generate a donut chart for Scope 1, 2, 3 emissions

        Args:
            category_data: Dict with keys like "Scope 1", "Scope 2", "Scope 3"

        Returns:
            Base64 encoded PNG image
        """
        if not category_data:
            return ""

        labels = ["Scope 1", "Scope 2", "Scope 3"]
        values = [category_data.get(label, 0) for label in labels]
        colors = ["#4f46e5", "#10b981", "#f97316"]

        # Filter out zero values
        filtered_data = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
        if not filtered_data:
            return ""

        labels, values, colors = zip(*filtered_data)

        fig, ax = plt.subplots(figsize=(3.8, 3.8))
        ax.set_aspect("equal", adjustable="datalim")

        wedges, texts = ax.pie(
            values,
            labels=None,
            colors=colors,
            startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 2},
            textprops={"fontsize": 11, "weight": "bold"},
        )

        # Create donut hole
        centre_circle = plt.Circle((0, 0), 0.70, fc="white")
        fig.gca().add_artist(centre_circle)
        ax.set_aspect("equal")

        # Add custom labels with percentages
        total = sum(values)
        for i, (wedge, label, value) in enumerate(zip(wedges, labels, values)):
            if value > 0:
                angle = (wedge.theta2 - wedge.theta1) / 2 + wedge.theta1
                x = 1.3 * wedge.r * plt.np.cos(plt.np.deg2rad(angle))
                y = 1.3 * wedge.r * plt.np.sin(plt.np.deg2rad(angle))

                percentage = (value / total) * 100
                ax.annotate(
                    f"{label}\n{percentage:.1f}%",
                    xy=(
                        wedge.r * plt.np.cos(plt.np.deg2rad(angle)),
                        wedge.r * plt.np.sin(plt.np.deg2rad(angle)),
                    ),
                    xytext=(x, y),
                    ha="center",
                    va="center",
                    fontsize=9,
                    weight="bold",
                    arrowprops=dict(
                        arrowstyle="-", connectionstyle="arc3,rad=0", color="gray", lw=1
                    ),
                )

        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", transparent=True)
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode("utf-8")

    @classmethod
    def generate_line_chart(
        cls, multi_year_data: Dict[int, Dict[str, float]], year_range: list
    ) -> str:
        """
        Generate a multi-year line chart showing emissions trends

        Args:
            multi_year_data: Dict mapping years to monthly data
            year_range: List of years to display

        Returns:
            Base64 encoded PNG image
        """
        if not multi_year_data or not year_range:
            return ""

        fig, ax = plt.subplots(figsize=(10, 5))

        month_indices = list(range(1, 13))
        colors = ["#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]

        for idx, year in enumerate(year_range):
            if year in multi_year_data:
                monthly_values = [
                    multi_year_data[year].get(month, 0) for month in cls.MONTH_NAMES
                ]
                color = colors[idx % len(colors)]
                ax.plot(
                    month_indices,
                    monthly_values,
                    marker="o",
                    color=color,
                    label=str(year),
                    linewidth=2,
                )

        ax.set_xlabel("Month")
        ax.set_ylabel("Emissions (tCO$_2$e)")
        ax.set_title("Multi-Year Emissions Comparison")
        ax.set_xticks(month_indices)
        ax.set_xticklabels([m[:3] for m in cls.MONTH_NAMES])
        ax.legend(title="Year", loc="best")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return base64.b64encode(buf.read()).decode("utf-8")
