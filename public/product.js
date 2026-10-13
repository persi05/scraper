"use strict";

const id = Number(location.pathname.match(/^\/product\/(\d+)\/?$/)?.[1]);
const status = document.querySelector("#detail-status");

function setText(selector, value) {
  document.querySelector(selector).textContent = String(value ?? "-");
}

function detailField(list, label, value, className) {
  const pair = document.createElement("div");
  if (className) pair.className = className;
  const dt = document.createElement("dt");
  const dd = document.createElement("dd");
  dt.textContent = label;
  dd.textContent = String(value ?? "-");
  pair.append(dt, dd);
  list.append(pair);
}

async function start() {
  try {
    const response = await fetch("/catalog.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const catalogue = await response.json();
    const item = catalogue.products.find(product => product.id === id);
    if (!item) throw new Error("Przedmiot nie istnieje.");
    document.title = `${item.name} - Archiwum Przedmiotów`;
    setText("#detail-category", `${item.category} / ${item.rarity}`);
    setText("#detail-name", item.name);
    setText("#detail-description", item.description);
    const [whole, cents] = Number(item.price).toFixed(2).split(".");
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    const symbol = { PLN: "zł", EUR: "€", USD: "$" }[item.currency] || item.currency;
    const formattedPrice = `${grouped},${cents} ${symbol}`;
    setText("#detail-price", formattedPrice);
    setText("#detail-stats", item.stats);
    setText("#detail-enchantment", item.enchantment);
    const fields = document.querySelector("#detail-fields");
    for (const [label, key] of [
      ["ID oferty", "id"], ["Kategoria", "category"],
      ["Rzadkość", "rarity"], ["Poziom", "level"], ["Dostępność", "availability"],
      ["Ocena", "rating"], ["Liczba opinii", "reviews"], ["Data dodania", "added_at"],
      ["Edycja", "edition"], ["Region", "region"], ["Sprzedawca", "seller"],
      ["Dostawa", "shipping"], ["Stan", "condition"], ["Masa (g)", "weight_g"],
      ["Liczba sztuk", "stock"], ["Gwarancja (mies.)", "warranty_months"], ["Materiał", "material"],
      ["Obserwujący", "favorites"], ["Wyświetlenia", "views"], ["Typ oferty", "offer_type"],
      ["Zwrot (dni)", "return_days"], ["Opakowanie", "packaging"]
    ]) detailField(fields, label, item[key], `field-${key}`);
    status.hidden = true;
    document.querySelector("#product-detail").hidden = false;
  } catch (error) {
    status.textContent = `Nie udało się wczytać przedmiotu: ${error.message}`;
  }
}

start();
