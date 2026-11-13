"""Graphique production/consommation de la base lunaire.

Installation : python3 -m pip install matplotlib
Lancer : python3 production.py
Le fichier donnees_energie.json doit être à côté de ce script.
En mode cycle complet, lecture animée à 10 heures simulées/seconde.
En mode --direct du calculateur, suivi des nouvelles données du fichier.
"""
import json
from bisect import bisect_right
import math
import time
import tkinter as tk
from pathlib import Path
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------- PARAMÈTRES DE L'AFFICHAGE ----------
abscisse_H = 168
ordonne_kWH = 100
refresh_ms = 100
H_par_s = 10  # Vitesse de lecture du cycle complet
couleur_production = '#12ae65'
couleur_consommation = '#e34b4b'
fichier_json = Path(__file__).resolve().with_name('donnees_energie.json')


def lire_donnees():
    donnees = json.loads(fichier_json.read_text(encoding='utf-8'))
    mesures = donnees['données']
    if not isinstance(mesures, list) or not mesures:
        raise ValueError('Aucune mesure dans le fichier JSON.')
    precedent = -1
    for mesure in mesures:
        for cle in ('T-heure', 'production_kwh', 'consommation_kwh'):
            v = mesure[cle]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise ValueError(f'Valeur incorrecte : {cle}')
        if mesure['T-heure'] <= precedent:
            raise ValueError('Les mesures doivent être classées par heure croissante.')
        precedent = mesure['T-heure']
    return donnees


def lancer():
    fenetre = tk.Tk()
    fenetre.title('Base lunaire — production et consommation')
    fenetre.geometry('1050x600')
    fenetre.configure(bg='#303030')

    figure = Figure(figsize=(10, 4), facecolor='#303030')
    ax = figure.add_subplot(111)
    figure.subplots_adjust(left=.10, right=.96, bottom=.17, top=.80)
    ax.set_facecolor('#d9d9d9')
    ax.set_title('BILAN ÉNERGÉTIQUE — BASE LUNAIRE', color='white', fontsize=17, weight='bold', pad=22)
    ax.set_xlim(-abscisse_H, 0)
    ax.set_ylim(-3, ordonne_kWH * 1.05)
    graduations = [-abscisse_H * i / 4 for i in range(4, -1, -1)]
    ax.set_xticks(graduations, [f'T−{abs(x):g}h' for x in graduations])
    ax.set_ylabel('Énergie par heure (kWh)', color='white')
    ax.tick_params(colors='white')
    ax.grid(alpha=.2)
    for bord in ax.spines.values():
        bord.set_visible(False)

    courbe_production, = ax.plot([], [], color=couleur_production, linewidth=2, label='Production (kWh)')
    courbe_consommation, = ax.plot([], [], color=couleur_consommation, linewidth=2, label='Consommation (kWh)')
    point_production, = ax.plot([], [], 'o', color=couleur_production, markersize=6, clip_on=False)
    point_consommation, = ax.plot([], [], 'o', color=couleur_consommation, markersize=6, clip_on=False)
    ax.legend(loc='upper center', bbox_to_anchor=(.5, 1.02), ncol=2, frameon=False, labelcolor='white')

    canvas = FigureCanvasTkAgg(figure, master=fenetre)
    canvas.get_tk_widget().pack(fill='both', expand=True)
    valeur = tk.Label(fenetre, text='En attente de données…', bg='#303030', fg='white', font=('Arial', 14))
    valeur.pack(pady=(8, 5))
    statut = tk.Label(fenetre, bg='#303030', fg='white', font=('Arial', 11))
    statut.pack(pady=(0, 10))

    derniere_signature = None
    donnees = None
    debut_lecture = time.monotonic()
    dernier_temps = -1

    def recommencer():
        nonlocal debut_lecture
        debut_lecture = time.monotonic()

    tk.Button(fenetre, text='Recommencer la lecture du cycle', command=recommencer).pack(pady=(0, 10))

    def actualiser():
        nonlocal derniere_signature, donnees, debut_lecture, dernier_temps
        try:
            fichier = fichier_json.stat()
            signature = (fichier.st_mtime_ns, fichier.st_size)
            if signature != derniere_signature:
                nouvelles_donnees = lire_donnees()
                # Un fichier dont la dernière heure avance est suivi en direct.
                # Un fichier complet immobile est lu progressivement depuis T=0.
                if donnees is None or nouvelles_donnees['données'][-1]['T-heure'] < dernier_temps:
                    debut_lecture = time.monotonic()
                donnees = nouvelles_donnees
                derniere_signature = signature
                dernier_temps = donnees['données'][-1]['T-heure']

            mesures = donnees['données']
            temps = [m['T-heure'] for m in mesures]
            # Si le calculateur continue d'écrire, on affiche sa dernière mesure.
            # Sinon, on déroule le cycle déjà calculé à la vitesse configurée.
            age_fichier = time.time() - fichier.st_mtime
            mode_direct = age_fichier < 2.0 and len(mesures) < 708
            if mode_direct:
                indice = len(mesures) - 1
            else:
                cible = temps[0] + (time.monotonic() - debut_lecture) * H_par_s
                indice = max(0, bisect_right(temps, cible) - 1)
                indice = min(indice, len(mesures) - 1)

            maintenant = temps[indice]
            historique = [m for m in mesures[:indice + 1] if m['T-heure'] >= maintenant - abscisse_H]
            x = [m['T-heure'] - maintenant for m in historique]
            production = [m['production_kwh'] for m in historique]
            consommation = [m['consommation_kwh'] for m in historique]

            courbe_production.set_data(x, production)
            courbe_consommation.set_data(x, consommation)
            point_production.set_data([0], [production[-1]])
            point_consommation.set_data([0], [consommation[-1]])
            plafond = max(ordonne_kWH, max(production), max(consommation)) * 1.05
            ax.set_ylim(-.03 * plafond, plafond)
            valeur.config(text=(f'Production : {production[-1]:.2f} kWh   |   '
                                f'Consommation : {consommation[-1]:.2f} kWh   |   T+{maintenant:g} h'))
            batterie = historique[-1].get('batterie_%')
            infos = f'Batterie : {batterie:.1f} %' if isinstance(batterie, (int, float)) else ''
            if not mode_direct and indice == len(mesures) - 1:
                infos += '  •  Fin des données — Recommencer pour revoir'
            statut.config(text=infos, fg='white')
            canvas.draw_idle()
        except FileNotFoundError:
            statut.config(text='En attente de donnees_energie.json — lance calculateur.py.', fg='#ffda6b')
        except (OSError, ValueError, KeyError, TypeError, IndexError) as erreur:
            statut.config(text=f'Lecture impossible : {erreur}', fg='#ff9999')
        fenetre.after(refresh_ms, actualiser)

    actualiser()
    fenetre.mainloop()


if __name__ == '__main__':
    lancer()
