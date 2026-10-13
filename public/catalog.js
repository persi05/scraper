"use strict";

const pageNumber = Number(location.pathname.match(/^\/page\/(\d+)\/?$/)?.[1] || 1);
const tableBody = document.querySelector("#product-table");
const cardGrid = document.querySelector("#product-cards");
const status = document.querySelector("#status");
const loadButton = document.querySelector("#load-more");
let catalogue = null;
let pageItems = [];
let loadedCount = 0;
let loading = false;

const labels = {
  category: "Kategoria", rarity: "Rzadkość", level: "Poziom",
  availability: "Dostępność", rating: "Ocena", reviews: "Opinie", added_at: "Dodano"
};

function priceText(item) {
  const [whole, cents] = Number(item.price).toFixed(2).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const symbol = { PLN: "zł", EUR: "€", USD: "$" }[item.currency] || item.currency;
  return `${grouped},${cents} ${symbol}`;
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = String(content ?? "-");
  return node;
}

function productLink(item) {
  const link = element("a", "product-link", "Zobacz szczegóły →");
  link.href = `/product/${item.id}`;
  return link;
}

function tableRow(item) {
  const row = element("tr", "product-row");
  row.dataset.id = item.id;
  const nameCell = element("td", "name-cell");
  nameCell.append(element("strong", "", item.name), element("small", "", `ID ${item.id}`));
  row.append(nameCell);
  for (const key of ["category", "rarity", "level"]) row.append(element("td", `field-${key}`, item[key]));
  row.append(element("td", "field-price", priceText(item)));
  for (const key of ["availability", "rating", "reviews", "added_at"]) row.append(element("td", `field-${key}`, item[key]));
  const linkCell = element("td");
  linkCell.append(productLink(item));
  row.append(linkCell);
  return row;
}

function card(item) {
  const article = element("article", "product-card");
  article.dataset.id = item.id;
  const top = element("div", "card-top");
  top.append(element("span", "card-rarity", item.rarity));
  article.append(top, element("span", "card-category", item.category), element("h4", "", item.name));
  const fields = element("dl", "card-fields");
  const fieldKeys = ["level", "availability", "rating", "reviews", "added_at"];
  for (let index = fieldKeys.length - 1; index > 0; index--) {
    const randomIndex = Math.floor(Math.random() * (index + 1));
    [fieldKeys[index], fieldKeys[randomIndex]] = [fieldKeys[randomIndex], fieldKeys[index]];
  }
  for (const key of fieldKeys) {
    const pair = element("div");
    pair.append(element("dt", "", labels[key]), element("dd", "", item[key]));
    fields.append(pair);
  }
  article.append(fields);
  const bottom = element("div", "card-bottom");
  bottom.append(element("strong", "card-price", priceText(item)), productLink(item));
  article.append(bottom);
  return article;
}

function pageLinks() {
  const nav = document.querySelector("#pagination");
  nav.replaceChildren();
  for (let n = 1; n <= catalogue.pages.length; n++) {
    const link = element("a", n === pageNumber ? "active" : "", n);
    link.href = `/page/${n}`;
    if (n === pageNumber) link.setAttribute("aria-current", "page");
    link.setAttribute("aria-label", `Strona ${n}`);
    nav.append(link);
  }
}

function updateControls() {
  const count = pageItems.length;
  loadButton.hidden = loadedCount >= count;
  document.querySelector("#table-section").hidden = !tableBody.children.length;
  document.querySelector("#cards-section").hidden = !cardGrid.children.length;
  status.textContent = "";
}

function delay() {
  return new Promise(resolve => setTimeout(resolve, 300 + Math.floor(Math.random() * 1701)));
}

async function loadMore() {
  if (loading || loadedCount >= pageItems.length) return;
  loading = true;
  loadButton.disabled = true;
  status.textContent = "Wczytywanie porcji…";
  await delay();
  const end = Math.min(loadedCount + 20, pageItems.length);
  for (let index = loadedCount; index < end; index++) {
    const item = pageItems[index];
    if (index < 40) tableBody.append(tableRow(item));
    else cardGrid.append(card(item));
  }
  loadedCount = end;
  loading = false;
  loadButton.disabled = false;
  updateControls();
}

async function start() {
  try {
    const response = await fetch("/catalog.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    catalogue = await response.json();
    if (!catalogue.pages[pageNumber - 1]) throw new Error("Nie ma takiej strony katalogu.");
    const byId = new Map(catalogue.products.map(item => [item.id, item]));
    pageItems = catalogue.pages[pageNumber - 1].map(id => byId.get(id));
    pageLinks();
    await loadMore();
  } catch (error) {
    status.textContent = `Nie udało się wczytać katalogu: ${error.message}`;
  }
}

loadButton.addEventListener("click", loadMore);
start();
