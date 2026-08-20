(()=>{
  const card=document.querySelector(".payment-card");
  if(!card)return;
  const label=card.querySelector("small"),heading=card.querySelector("h3"),note=card.querySelector(".payment-note"),image=card.querySelector(".product-thumb"),link=card.querySelector("a.btn");
  if(label)label.textContent="FREE FOR A LIMITED TIME";
  if(heading)heading.textContent="GET YOUR TRACK IN ROTATION — FREE FOR NOW";
  if(note)note.textContent="Submit your track for review at no cost for a limited time. Approved music will be added to the AllThings140Radio continuous rotation.";
  if(image){image.src="/assets/allthings140-track-placement-free.webp?v=2";image.width=1200;image.height=900;image.alt="Free limited-time AllThings140Radio track placement"}
  if(link){link.href="#submissionForm";link.removeAttribute("target");link.textContent="SUBMIT YOUR TRACK FREE ↑"}
})();
