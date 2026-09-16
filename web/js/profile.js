/* ==========================================================================
   PROFILE — User Profile & About AI Rendering
   ========================================================================== */

function renderUserProfile(mem) {
  if (!mem) return;
  const profile = mem.profile || {};
  const prefs = mem.preferences || {};
  const visitors = mem.household_members_and_visitors || [];

  const nameEl = document.getElementById('prof-user-name');
  if (nameEl) nameEl.innerText = profile.preferred_name || 'Timilehin';

  const locEl = document.getElementById('prof-location');
  if (locEl) locEl.innerText = profile.location || 'Nigeria';

  const tzEl = document.getElementById('prof-timezone');
  if (tzEl) tzEl.innerText = profile.timezone || 'Africa/Lagos';

  const roleEl = document.getElementById('prof-user-role');
  if (roleEl && visitors.length > 0) {
    roleEl.innerText = visitors[0].role || 'Owner / Primary Resident';
  }

  // Favorite Series chips with Lucide Film SVG
  const series = (prefs.entertainment && prefs.entertainment.favorite_series) ? prefs.entertainment.favorite_series : [];
  const seriesEl = document.getElementById('prof-series-chips');
  if (seriesEl && series.length > 0) {
    seriesEl.innerHTML = series.map(s => `
      <span class="badge badge-secondary" style="font-size:0.775rem;">
        <span style="color:hsl(var(--muted-foreground));">${ICONS.film}</span>
        ${s}
      </span>
    `).join('');
  }

  // Favorite Genres
  const genres = (prefs.entertainment && prefs.entertainment.favorite_genres) ? prefs.entertainment.favorite_genres : [];
  const genreEl = document.getElementById('prof-genre-chips');
  if (genreEl && genres.length > 0) {
    genreEl.innerHTML = genres.map(g => `
      <span class="badge badge-outline" style="font-size:0.775rem;">${g}</span>
    `).join('');
  }
}

function renderAboutAI(asst) {
  if (!asst) return;
  const asstName = asst.name || 'Nova';
  const nameEl = document.getElementById('about-ai-name');
  if (nameEl) nameEl.innerText = asstName;

  const titleEl = document.getElementById('about-ai-dossier-title');
  if (titleEl) titleEl.innerText = `${asstName} Assistant Dossier`;

  const descEl = document.getElementById('about-ai-directives-desc');
  if (descEl) descEl.innerText = `Core operational directives programmed into ${asstName}'s system prompt.`;
}
window.renderAboutAI = renderAboutAI;
