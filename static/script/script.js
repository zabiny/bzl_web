const date = new Date();
const year = date.getFullYear();

document.getElementById("zak").innerHTML = year - 13;
document.getElementById("veteran").innerHTML = year - 45;

if (Math.random() < 0.005)
{
    document.getElementById("easter-egg").src = "/static/runner69.png";
}