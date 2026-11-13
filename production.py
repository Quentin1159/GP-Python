"""Affichage seulement : python3 production.py
Installation : python3 -m pip install matplotlib
Lancer calculateur.py pour générer le cycle complet.
Pour le mode progressif : python3 calculateur.py --direct
"""
import json
import math
import time
import tkinter as tk
from pathlib import Path
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------- PARAMÈTRES DE L'AFFICHAGE ----------
abscisse_H = 168
ordonne_kWH = 100  # Échelle du graphique seulement ; aucun calcul physique ici.
y_min, y_max = 0, ordonne_kWH * 1.05
refresh_ms = 100
titre = 'PRODUCTION D’ÉNERGIE — BASE LUNAIRE'
unite = 'kWh'
couleur = '#12ae65'
fichier_json = Path(__file__).resolve().with_name('donnees_energie.json')
# delta_t_H et H_par_s sont définis par calculateur.py et lus dans le JSON.


def lire_donnees():
    donnees = json.loads(fichier_json.read_text(encoding='utf-8'))
    if donnees.get('version') != 2:
        raise ValueError('Regénère le JSON avec le nouveau calculateur (version 2).')
    if donnees.get('colonnes') != ['temps_H', 'energie_produite_kWh', 'energie_consommee_kWh']:
        raise ValueError('Ordre des colonnes JSON incorrect.')
    for cle in ('delta_t_H', 'H_par_s', 'duree_integration_H'):
        v = donnees[cle]
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f'Valeur incorrecte : {cle}.')
    mesures = donnees['mesures']
    if not isinstance(mesures, list) or not mesures:
        raise ValueError('Aucune mesure disponible.')
    precedent = -math.inf
    for mesure in mesures:
        if not isinstance(mesure, list) or len(mesure) != 3:
            raise ValueError('Chaque mesure doit contenir trois nombres.')
        for cle, v in zip(donnees['colonnes'], mesure):
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f'Mesure incorrecte : {cle}.')
        if mesure[0] <= precedent:
            raise ValueError('Les mesures doivent être classées par temps croissant.')
        precedent = mesure[0]
    return donnees


def lancer():
    fenetre = tk.Tk()
    fenetre.title('Base lunaire — production solaire')
    fenetre.geometry('1000x550')
    fenetre.configure(bg='#303030')

    figure = Figure(figsize=(10, 4), facecolor='#303030')
    ax = figure.add_subplot(111)
    figure.subplots_adjust(left=.10, right=.96, bottom=.17, top=.85)
    ax.set_facecolor('#d9d9d9')
    ax.set_title(titre, color='white', fontsize=17, weight='bold', pad=18)
    ax.set_xlim(-abscisse_H, 0)
    ax.set_ylim(y_min, y_max)
    graduations = [-abscisse_H * i / 4 for i in range(4, -1, -1)]
    ax.set_xticks(graduations, [f'T−{abs(x):g}h' for x in graduations])
    ax.set_ylabel('Énergie sur l’heure précédente (kWh)', color='white')
    ax.tick_params(colors='white')
    ax.grid(alpha=.2)
    for bord in ax.spines.values():
        bord.set_visible(False)

    courbe, = ax.plot([], [], color=couleur, linewidth=2, marker='o', markersize=3)
    point, = ax.plot([], [], 'o', color=couleur, markersize=6)
    canvas = FigureCanvasTkAgg(figure, master=fenetre)
    canvas.get_tk_widget().pack(fill='both', expand=True)
    valeur = tk.Label(fenetre, text='En attente de données…', bg='#303030', fg='white', font=('Arial', 16))
    valeur.pack(pady=(10, 5))
    statut = tk.Label(fenetre, bg='#303030', fg='white', font=('Arial', 11))
    statut.pack(pady=(0, 15))
    derniere_signature = None
    infos = ''
    delai_inactivite = 5
    mode = "direct"

    def actualiser():
        nonlocal derniere_signature, infos, delai_inactivite, mode
        try:
            fichier = fichier_json.stat()
            signature = (fichier.st_mtime_ns, fichier.st_size)
            if signature != derniere_signature:
                donnees = lire_donnees()
                mode = donnees.get('mode', 'direct')
                delta_t_H = donnees['delta_t_H']
                H_par_s = donnees['H_par_s']
                maintenant = donnees['mesures'][-1][0]
                historique = [m for m in donnees['mesures'] if m[0] >= maintenant - abscisse_H]
                x = [m[0] - maintenant for m in historique]
                y = [m[1] for m in historique]
                courbe.set_data(x, y)
                point.set_data([0], [y[-1]])
                ax.set_ylim(y_min, max(y_max, max(y) * 1.05))
                valeur.config(text=f'Dernière heure : {y[-1]:.2f} {unite}  |  Temps simulé : {maintenant:.1f} h')
                infos = f'Pas : {delta_t_H:g} h • Énergie sur {donnees["duree_integration_H"]:g} h • Vitesse : {H_par_s:g} h/s'
                if mode == 'cycle_complet':
                    infos = f'Cycle complet chargé • Pas : {delta_t_H:g} h • Fenêtre affichée : {abscisse_H:g} h'
                delai_inactivite = max(5, 3 * delta_t_H / H_par_s)
                canvas.draw_idle()
                derniere_signature = signature
            inactif = mode != 'cycle_complet' and time.time() - fichier.st_mtime > delai_inactivite
            statut.config(text=infos + (' • Données non actualisées : calculateur arrêté ?' if inactif else ''), fg='white')
        except FileNotFoundError:
            statut.config(text='En attente de donnees_energie.json — lance calculateur.py.', fg='#ffda6b')
        except (OSError, ValueError, KeyError, TypeError, IndexError) as erreur:
            statut.config(text=f'Lecture impossible : {erreur}', fg='#ff9999')
        fenetre.after(refresh_ms, actualiser)

    actualiser()
    fenetre.mainloop()


if __name__ == '__main__':
    lancer()
