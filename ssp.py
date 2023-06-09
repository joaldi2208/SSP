import sys
import os
import pandas as pd
import numpy as np

import warnings
warnings.filterwarnings("ignore", message=".*The 'nopython' keyword.*")

from catboost import CatBoostRegressor

from bruker.api.topspin import Topspin
from bruker.data.nmr import *

class SecStrucPredictor():
    """predicts the three state secondary structure (helix, sheet and coil) of a protein from an N-HSQC spectra"""
    
    def __init__(self):
        """initializes the input matrices and loads the predictor model"""
        self.predictor = CatBoostRegressor()
        self.predictor.load_model("/opt/topspin4.2.0/python/examples/SSP/Model.cbm")
    

    def get_input(self, input_matrices):
        """reads input matrix"""
        self.matrix_20x10 = input_matrices[0]
        self.matrix_26x10 = input_matrices[1]
        self.matrix_10x8 = input_matrices[2]

        return self
    

    def combine_inputs(self):
        """combines and reshapes the input matrices"""
        self.matrix_20x10_1D = self.matrix_20x10.reshape(-1)
        self.matrix_26x10_1D = self.matrix_26x10.reshape(-1)
        self.matrix_10x8_1D = self.matrix_10x8.reshape(-1)

        self.combined_inputs = list(self.matrix_20x10_1D) + list(self.matrix_26x10_1D) + list(self.matrix_10x8_1D)

        return self


    def predict_structure_composition(self):
        self.predictions = self.predictor.predict(self.combined_inputs)

        return self.predictions 

    
    def calc_shap_values(self):
        """calulates shap values for 540 quadrants for one sample"""

        explainer = shap.TreeExplainer(self.predictor)
        self.shap_values = explainer.shap_values([self.combined_inputs], [self.predictions])

        return self


    def build_shap_spectra(self):
        """builds spectra based on calculated shap values"""
        
        fig, axs = plt.subplots(figsize=((15,10)), nrows=3, ncols=3)
        fig.suptitle("Shap Values")

        for i, (sec_struc_type, bin_type) in enumerate(zip(["Coil", "Sheet", "Helix"], ["20x10", "26x10", "10x8"])):
            axs[0][i].set_title(bin_type)
            axs[2][i].set_xlabel("H-shift in ppm", fontsize=13)
            axs[i,0].set_ylabel(sec_struc_type + "\n N-Shift in ppm", fontsize=13)
            spectra_20x10 = self.shap_values[i].ravel()[:200].reshape(20,10)
            spectra_26x10 = self.shap_values[i].ravel()[200:460].reshape(26,10)
            spectra_10x8 = self.shap_values[i].ravel()[460:].reshape(10,8)
         
            spectra = [spectra_20x10, spectra_26x10, spectra_10x8]

            for ii, (spec, x, y, H_scale, N_scale) in enumerate(zip(spectra, [10,10,8], [20,26,10], [0.5,0.5,0.625], [2.5,1.9230769230769231,5])):

                im = axs[i][ii].imshow(spec, cmap="tab20c", vmax=0.032, vmin=-0.032)    
                cbar = fig.colorbar(im, extend="both")
                axs[i][ii].set_xticks(np.arange(x))
                axs[i][ii].set_yticks(np.arange(y))

                #axs[i][ii].set_xlabel("H-Shift in ppm")
                #axs[i][ii].set_ylabel("N-Shift in ppm")

                axs[i][ii].set_xticks(np.arange(x), [str(round(i,1)) for i in np.arange(6,11,H_scale)], rotation=45)
                axs[i][ii].set_yticks(np.arange(y), [str(round(i,1)) for i in np.arange(90,140,N_scale)])
                
                axs[i][ii].set_xlim(x-0.5,-0.5)

        plt.tight_layout()
        plt.show()

    
def binning(shifts, binsize, shift_min, num_1D_grid):
    """gives the indexes for certain bins by float dividing the shift value by the binsize"""
    bin_indexes = []
    for ppm_value in shifts:
    
        bin_index = int((ppm_value - shift_min) // binsize)
        if bin_index > (num_1D_grid - 1): # to large for set grid limits
            continue # ignore peak
            # bin_index = num_1D_grid - 1 # append to largest quadrant
        elif bin_index < 0: # to small for set grid limits
            continue # ignore peak
            # bin_index = 0 # append to smallest quadrant
        
        bin_indexes.append(bin_index)


    return bin_indexes


def get_shifts(chemical_shifts, atomtype):
    """returns a list of with all shifts of a certain atomtype. X stands for H and Y for N"""
    shifts = []

    for NMR_data in chemical_shifts.values():
        shifts_one_protein = NMR_data[f"{atomtype}_shift"].to_numpy()
        shifts.append(shifts_one_protein)

    return shifts
    

def generate_count_peaks_matrix(binned_H_shifts, binned_N_shifts, H_num_1D_grid, N_num_1D_grid):
    """counts peaks in a certain bin in the defined 2D grid"""
    grid_2D = (N_num_1D_grid, H_num_1D_grid)
    count_peaks_matrix = np.zeros(grid_2D)
    
    for H_shift_bin, N_shift_bin in zip(binned_H_shifts, binned_N_shifts):
        count_peaks_matrix[N_shift_bin, H_shift_bin] += 1

    return count_peaks_matrix
    

if __name__ == "__main__":

    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+")
        print("Ubiquitin prediction from 5387 backbone spectrum of the BMRB")
        print("*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+*+")
        peak_list = pd.read_csv("/opt/topspin4.2.0/python/examples/SSP/BMRB_peak_list_ubiquitin.csv")
        N_shifts = peak_list["Y_shift"].to_list()
        H_shifts = peak_list["X_shift"].to_list()

    elif len(sys.argv) > 1 and sys.argv[1].endswith(".csv"):
        print("# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # ")
        print(f"Spectrum prediction from {os.getcwd() + '/' + sys.argv[1]}")
        print("# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # ")
        peak_list = pd.read_csv(sys.argv[1])
        #N_shifts = peak_list["x(F1) [ppm]"].to_list()
        #H_shifts = peak_list["x(F2) [ppm]"].to_list()
        N_shifts = peak_list["Y_shift"].to_list()
        H_shifts = peak_list["X_shift"].to_list()

    else:
        top = Topspin()
        dp = top.getDataProvider()

        hsqc = dp.getCurrentDataset()

        peak_list = hsqc.getPeakList()

        if len(peak_list) == 0:
            raise ValueError("NO PEAKS SELECTED! Use the pp command or select the peaks manually!")

        
        H_shifts = []
        N_shifts = []

        max_intensity = np.max([peak["intensity"] for peak in peak_list])
        
        for peak in peak_list:
            rel_intensity = peak["intensity"] / max_intensity
            if rel_intensity > 0: # negative intensity ==> sidechain NH(2) ### here you can adjust sensitivity!!!!!!!!!!!!!!!!!!!!!!
                H_shifts.append(peak["position"][0])
                N_shifts.append(peak["position"][1])


    predictor = SecStrucPredictor() 

    input_matrices = []
    
    H_shift_max = 11
    H_shift_min = 6 

    N_shift_max = 140 
    N_shift_min = 90
    
    for H_num_1D_grid, N_num_1D_grid in [(10,20),(10,26),(8,10)]:
    
        H_binsize = (H_shift_max - H_shift_min) / H_num_1D_grid
        N_binsize = (N_shift_max - N_shift_min) / N_num_1D_grid
    

        binned_H_shifts = binning(H_shifts, H_binsize, H_shift_min, H_num_1D_grid)
        binned_N_shifts = binning(N_shifts, N_binsize, N_shift_min, N_num_1D_grid)

        count_peaks_matrixes = generate_count_peaks_matrix(binned_H_shifts, binned_N_shifts, H_num_1D_grid, N_num_1D_grid)

        input_matrices.append(count_peaks_matrixes)

    
    predictor.get_input(input_matrices)
    predictor.combine_inputs()
    prediction = predictor.predict_structure_composition()

    print(f" Secondary Structure Prediction \n -------------------------------- \n Helix: {round(prediction[2],3)*100:.1f}%  \n Sheet: {round(prediction[1],3)*100:.1f}% \n Coil: {round(prediction[0],3)*100:.1f}%")
    
    #print("I need to update the requirement file")

    if "shap" in sys.argv:
        import matplotlib.pyplot as plt
        import shap
        predictor.calc_shap_values()
        predictor.build_shap_spectra()

    if sys.argv[1] == "test":
        if str(21.2) == str(round(prediction[2],3)*100)[:4] and str(36.1) ==str(round(prediction[1],3)*100)[:4] and str(42.8) == str(round(prediction[0],3)*100)[:4]:
            print("\n \n \t \t <<< PREDICTION TEST PASSED >>> ")
        else:
            print("\n \n \t \t >>> PREDICTION TEST FAILED!!!!!!! <<< ")
            print("Possibly you are currently using a different model") 
