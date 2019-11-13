#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @author Alwin Ebermann (alwin@alwin.net.au)
# @author Markus Pielmeier

from datetime import datetime, timedelta, date
from enum import Enum

import requests
from bs4 import BeautifulSoup

MENSEN = {
    421: "Mensa Arcisstr.",
    411: "Mensa Leopoldstr.",
    422: "Mensa Garching",
    412: "Mensa Martinsried",
    423: "Mensa Weihenstephan",
    432: "Mensa Pasing"
}

MEAL_URL_TEMPLATE = "https://www.studentenwerk-muenchen.de/mensa/speiseplan/speiseplan_{date}_{id}_-de.html"


class Category(Enum):
    BEEF = ("🐄",)
    PORK = ("🐷",)
    VEGGY = ("🥕",)
    VEGAN = ("🥑",)

    def __init__(self, emoji):
        self.emoji = emoji

    def __str__(self):
        return self.emoji


class Meal:
    def __init__(self, name: str, typ: str):
        self.name = name
        self.categories = set()
        self.typ = typ

    def add_category(self, category: Category):
        self.categories.add(category)

    def is_meatless(self):
        return (Category.VEGAN in self.categories) or (Category.VEGGY in self.categories)

    def is_vegan(self):
        return Category.VEGAN in self.categories

    def __str__(self):
        return self.name + " " + "".join(map(str, self.categories))


class Menu:
    def __init__(self, mensa_id: int, date: str):
        self.mensa = MENSEN.get(mensa_id, "???")
        self.meals = []
        self.date = date

    def add_meal(self, meal: Meal):
        self.meals.append(meal)

    def get_meals(self, filter_mode: str):
        meals = []
        for meal in self.meals:
            if filter_mode == "none":
                meals.append(meal)
            elif filter_mode == "vegetarian" and meal.is_meatless():
                meals.append(meal)
            elif filter_mode == "vegan" and meal.is_vegan():
                meals.append(meal)
        return meals

    def get_date(self):
        return self.date

    def get_meals_message(self, filter_mode: str = "none"):
        if self.is_closed():
            return f"{self.mensa} ist am {self.date} geschlossen"

        filtered = self.get_meals(filter_mode)
        if len(filtered) == 0:
            return "Keine Essen entsprechen dem gewählten Filter."

        out = f"*{self.mensa}* am *{self.date}*\n"

        last_typ = None
        for meal in self.meals:
            if meal.typ != last_typ:
                out += f"\n*{meal.typ}*:"
                last_typ = meal.typ
            out += "\n" + str(meal)

        if filter_mode == "none" or filter_mode == "vegetarian":
            out += "\n🥑 = vegan, 🥕 = vegetarisch"
        if filter_mode == "none":
            out += "\n🐷 = Schwein, 🐄 = Rind"

        return out

    def is_closed(self):
        return len(self.meals) == 0


class MenuManager:

    @staticmethod
    def download_next_menu(mensa_id):
        now = datetime.now()
        day = date.today()

        if now.weekday() in (5, 6):
            # weekend
            # skip to next monday
            day += timedelta(days=7 - now.weekday())
        elif now.hour > 15:
            # afternoon during workdays
            # show next day
            day += timedelta(days=1)

        for _ in range(20):
            url = MEAL_URL_TEMPLATE.format(date=day.isoformat(), id=mensa_id)
            print("downloading", url)
            r = requests.get(url)

            if r.status_code == 200:
                return r.content, day
            elif r.status_code == 404:
                day += timedelta(days=1)
                continue
            else:
                r.raise_for_status()
        return None, None

    def get_menu(self, mensa_id: int):
        content, day = self.download_next_menu(mensa_id)
        soup = BeautifulSoup(content, "lxml")

        menu = Menu(mensa_id, day.strftime("%d.%m.%Y"))

        last_type = ""
        for meal_tag in soup.select(".c-schedule__list-item"):
            type_str = meal_tag.select(".stwm-artname")[0].string
            if type_str is None or type_str == "":
                type_str = last_type
            last_type = type_str
            mealname = meal_tag.select(".js-schedule-dish-description")[0].find(text=True, recursive=False)

            meal = Meal(mealname, type_str)

            icons = meal_tag.select(".c-schedule__icon span")
            if len(icons) > 0:
                if "vegan" in icons[0]["class"]:
                    meal.add_category(Category.VEGAN)
                if "fleischlos" in icons[0]["class"]:
                    meal.add_category(Category.VEGGY)

            sup = meal_tag.select(".u-text-sup")
            if len(sup) > 0:
                if "S" in sup[0].text:
                    meal.add_category(Category.PORK)
                if "R" in sup[0].text:
                    meal.add_category(Category.BEEF)
            menu.add_meal(meal)
        return menu

