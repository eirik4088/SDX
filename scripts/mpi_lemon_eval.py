import pathlib
import mne
from multiprocessing import Process
import numpy as np
from meegkit import dss
from eeg_clean import clean_new
from eeg_clean.epoch_stats import EpochStats
from data_quality import ica_score
from autoreject import AutoReject
from pyprep import PrepPipeline

data_set = pathlib.Path(r"C:\Users\workbench\eirik_master\Data\mpi_lemon")
save_folder = pathlib.Path(
    r"C:\Users\workbench\eirik_master\Results\mpi_lemon"
)

subjects = []
for pth in data_set.rglob("*.vhdr"):
    subjects.append(pth)

random_start = [
    [0, 4, 2, 6, 4, 6, 0, 4, 4, 0, 4, 6, 0, 6, 4, 6, 6, 2, 0, 4, 0, 2, 6, 0, 6, 0, 6, 2, 6, 6, 2, 6, 6, 0, 2, 0, 6, 4, 0, 2, 6, 6, 0, 6, 2, 6, 6, 2, 0, 0, 6, 0, 4, 6, 2, 2, 0, 2, 6, 4, 6, 0, 4, 2, 0, 6, 4, 6, 0, 6, 6, 4, 2, 4, 4, 6, 4, 2, 4, 2, 4, 6, 2, 2, 2, 4, 2, 4, 2, 0, 6, 2, 2, 4, 6, 2, 4, 2, 0, 0, 2, 6, 0, 2, 0, 4, 0, 0, 0, 0, 0, 0, 4, 6, 0, 6, 4, 0, 4, 4, 6, 0, 2, 6, 0, 2, 6, 4, 6, 2, 4, 0, 4, 6, 4, 4, 2, 4, 2, 0, 4, 4, 2, 4, 4, 4, 4, 6, 0, 4, 6, 0, 2, 4, 6, 0, 0, 0, 0, 0, 6, 0, 0, 6, 4, 0, 4, 6, 6, 0, 2, 6, 4, 6, 0, 2, 4, 2, 2, 4, 2, 6, 4, 6, 2, 4, 0, 0, 6, 6, 2, 6, 2, 2, 6, 0, 2, 2, 4, 2, 6, 4, 2, 0, 2, 6, 0, 2, 2, 0, 2, 4],
    [5, 3, 3, 3, 7, 7, 5, 3, 7, 1, 5, 5, 1, 1, 5, 3, 5, 7, 7, 3, 3, 5, 5, 3, 5, 3, 3, 1, 3, 1, 5, 7, 5, 1, 3, 3, 1, 7, 7, 3, 1, 7, 1, 5, 1, 5, 7, 1, 5, 3, 3, 7, 1, 3, 1, 1, 5, 3, 1, 5, 1, 3, 7, 5, 7, 5, 3, 7, 1, 7, 7, 5, 7, 5, 7, 1, 7, 1, 5, 1, 7, 7, 1, 1, 3, 3, 5, 5, 3, 7, 5, 1, 1, 5, 5, 7, 7, 1, 5, 5, 3, 7, 3, 5, 7, 5, 3, 3, 5, 1, 3, 5, 5, 1, 7, 7, 5, 3, 1, 1, 1, 3, 7, 1, 3, 3, 5, 3, 5, 7, 1, 3, 1, 1, 7, 5, 5, 1, 7, 5, 3, 3, 1, 5, 5, 7, 1, 1, 1, 3, 5, 5, 5, 5, 7, 5, 7, 1, 3, 1, 7, 1, 3, 5, 3, 7, 3, 5, 1, 3, 7, 1, 7, 1, 1, 7, 7, 1, 5, 3, 1, 5, 1, 7, 7, 3, 7, 3, 7, 3, 5, 3, 5, 7, 3, 7, 3, 7, 1, 3, 7, 7, 3, 7, 7, 5, 7, 5, 5, 7, 7, 5],
]


def zapline_clean(raw, fline):
    data = raw.get_data(verbose=False).T  # Convert mne data to numpy darray
    sfreq = raw.info["sfreq"]  # Extract the sampling freq
    # Apply MEEGkit toolbox function
    out, _ = dss.dss_line(
        data, fline, sfreq, nkeep=1, show=False
    )  # fline (Line noise freq) = 50 Hz for Europe
    cleaned_raw = mne.io.RawArray(
        out.T, raw.info, verbose=False
    )  # Convert output to mne RawArray again

    return cleaned_raw

def get_event_times(mne_raw):
    events, _ = mne.events_from_annotations(mne_raw, event_id="auto", verbose=False)
    ec = 210
    eo = 200
    start_times = []
    end_times = []
    previous = [np.inf, np.inf, np.inf]

    for i in events:
        if i[2] == ec and previous[2] != ec:
            start_times.append(i[0] / 2500)
        elif i[2] == eo and previous[2] != eo:
            start_times.append(i[0] / 2500)
        if previous[2] == ec and i[2] != ec:
            end_times.append(previous[0] / 2500)
        elif previous[2] == eo and i[2] != eo:
            end_times.append(previous[0] / 2500)

        previous = i

    return start_times, end_times


def evaluate(processor, to_fill: np.ndarray, baseline=None):

    if processor.bad_channels is not None:
        to_fill[0] = len(processor.bad_channels) / 61
    else:

        if baseline is not None:
            return

        to_fill[0] = 0

    if to_fill[0] < 0.73:
        for_ica = processor.epochs_obj.copy()
        for_ica.set_eeg_reference(verbose=False)

        evaluater = ica_score.IcaScore(for_ica)
        to_fill[1] = evaluater.get_n_components()[0]
        to_fill[2] = evaluater.get_n_components()[0] + evaluater.get_n_components()[1]
        to_fill[3] = evaluater.get_explained_var()["eeg"]
        to_fill[4] = evaluater.get_explained_var(bio_components=True)["eeg"]
        if baseline is not None:
            to_fill[1] = to_fill[1] - baseline[1]
            to_fill[2] = to_fill[2] - baseline[2]
            to_fill[3] = to_fill[3] - baseline[3]
            to_fill[4] = to_fill[4] - baseline[4]
    else:
        to_fill[1:] = float("nan")


def evaluate_other(epochs, bad_channels, to_fill: np.ndarray, baseline=None):

    if len(bad_channels) > 0:
        to_fill[0] = len(bad_channels) / 61
    else:

        if baseline is not None:
            return

        to_fill[0] = 0

    if to_fill[0] < 0.73:
        epochs.set_eeg_reference(verbose=False)

        evaluater = ica_score.IcaScore(epochs)
        to_fill[1] = evaluater.get_n_components()[0]
        to_fill[2] = evaluater.get_n_components()[0] + evaluater.get_n_components()[1]
        to_fill[3] = evaluater.get_explained_var()["eeg"]
        to_fill[4] = evaluater.get_explained_var(bio_components=True)["eeg"]
        if baseline is not None:
            to_fill[1] = to_fill[1] - baseline[1]
            to_fill[2] = to_fill[2] - baseline[2]
            to_fill[3] = to_fill[3] - baseline[3]
            to_fill[4] = to_fill[4] - baseline[4]
    else:
        to_fill[1:] = float("nan")


def process(my_index):

    raw = mne.io.read_raw_brainvision(subjects[my_index], verbose=False)
    raw.drop_channels("VEOG")
    raw.set_montage("standard_1020", verbose=False)

    start_times, end_times = get_event_times(raw)

    for eye in range(2):
        base_line = np.zeros(5)
        results = np.zeros((5, 5))
        cond = (
            raw.copy()
            .crop(
                start_times[random_start[eye][my_index]],
                end_times[random_start[eye][my_index]],
            )
            .load_data()
        ).resample(sfreq=201, verbose=False)

        cond.filter(l_freq=1, h_freq=None, verbose=False)
        cond.filter(l_freq=None, h_freq=100, verbose=False)
        cond = zapline_clean(cond, 50)
        #cond.resample(sfreq=201, verbose=False)
        epochs = mne.make_fixed_length_epochs(cond, 0.5, verbose=False, preload=True)

        base_processor = clean_new.CleanNew(
            epochs.copy(), dist_specifics={"dummy_key": None}, thresholds=[None]
        )
        evaluate(base_processor, base_line)
        base_stats = EpochStats(base_processor.epochs_obj.copy())
        base_stats.calc_stability()
        np.save(save_folder / str(eye) / "accumulate" / "base_line"/ "peaks" / "abs_dis" / str(my_index), base_stats.get_peak_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "base_line"/ "peaks" / "dis" / str(my_index), base_stats.get_peak_stability().get_mean_stab())
        np.save(save_folder / str(eye) / "accumulate" / "base_line"/ "quasi" / "abs_dis" / str(my_index), base_stats.get_quasi_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "base_line"/ "quasi" / "dis" / str(my_index), base_stats.get_quasi_stability().get_mean_stab())

        my_processor = clean_new.CleanNew(
            epochs.copy(),
            thresholds=[2.5, 3],
            dist_specifics={
                "quasi": {
                    "central": "mean",
                    "spred_corrected": "IQR",
                },
                "peak": {
                    "central": "mean",
                    "spred_corrected": "IQR",
                },
            },
        )
        evaluate(
            my_processor,
            results[0, :],
            base_line,
        )

        if len(my_processor.bad_channels) > 0:
            stats = EpochStats(my_processor.epochs_obj.copy())
            np.save(save_folder / str(eye) / "bad_channels" / "my_heavy"/ str(my_index), my_processor.bad_channels)
        else:
            stats = EpochStats(epochs.copy())

        stats.calc_stability()
        np.save(save_folder / str(eye) / "accumulate" / "my_heavy"/ "peaks" / "abs_dis" / str(my_index), stats.get_peak_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "my_heavy"/ "peaks" / "dis" / str(my_index), stats.get_peak_stability().get_mean_stab())
        np.save(save_folder / str(eye) / "accumulate" / "my_heavy"/ "quasi" / "abs_dis" / str(my_index), stats.get_quasi_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "my_heavy"/ "quasi" / "dis" / str(my_index), stats.get_quasi_stability().get_mean_stab())

        my_processor = clean_new.CleanNew(
            epochs.copy(),
            thresholds=[4.5, 5.5],
            dist_specifics={
                "quasi": {
                    "central": "mean",
                    "spred_corrected": "IQR",
                },
                "peak": {
                    "central": "median",
                    "spred_corrected": "IQR",
                },
            },
        )
        evaluate(
            my_processor,
            results[1, :],
            base_line,
        )

        if len(my_processor.bad_channels) > 0:
            stats = EpochStats(my_processor.epochs_obj.copy())
            np.save(save_folder / str(eye) / "bad_channels" / "my_light"/ str(my_index), my_processor.bad_channels)
        else:
            stats = EpochStats(epochs.copy())

        stats.calc_stability()
        np.save(save_folder / str(eye) / "accumulate" / "my_light"/ "peaks" / "abs_dis" / str(my_index), stats.get_peak_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "my_light"/ "peaks" / "dis" / str(my_index), stats.get_peak_stability().get_mean_stab())
        np.save(save_folder / str(eye) / "accumulate" / "my_light"/ "quasi" / "abs_dis" / str(my_index), stats.get_quasi_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "my_light"/ "quasi" / "dis" / str(my_index), stats.get_quasi_stability().get_mean_stab())

        epochs_copy = epochs.copy()
        epochs_copy.set_eeg_reference(verbose=False)

        # Create autoreject object and fit it with the data
        reject = AutoReject(
            consensus=[1.0], n_interpolate=[0], random_state=97, verbose=False
        )
        reject.fit(epochs_copy)
        # find where channels are considered bad, and extract the ones that are bad longer then threshold percentage
        log = reject.get_reject_log(epochs_copy)
        n_epochs = len(epochs)
        n_bads = log.labels.sum(axis=0)
        # Index of bad channels, drop them and evaluate...
        bads_index = np.where(n_bads > n_epochs * 0.45)[0]

        if bads_index.size > 0:
            bads_name_autorej = [epochs_copy.ch_names[idx] for idx in bads_index]
            epochs_copy.drop_channels(bads_name_autorej)
        else:
            bads_name_autorej = []

        evaluate_other(epochs_copy, bads_name_autorej, results[2, :], base_line)

        if len(bads_name_autorej) > 0:
            stats = EpochStats(epochs_copy.copy())
            np.save(save_folder / str(eye) / "bad_channels" / "heavy_auto"/ str(my_index), np.array(bads_name_autorej))
        else:
            stats = EpochStats(epochs.copy())

        stats.calc_stability()
        np.save(save_folder / str(eye) / "accumulate" / "heavy_auto"/ "peaks" / "abs_dis" / str(my_index), stats.get_peak_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "heavy_auto"/ "peaks" / "dis" / str(my_index), stats.get_peak_stability().get_mean_stab())
        np.save(save_folder / str(eye) / "accumulate" / "heavy_auto"/ "quasi" / "abs_dis" / str(my_index), stats.get_quasi_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "heavy_auto"/ "quasi" / "dis" / str(my_index), stats.get_quasi_stability().get_mean_stab())

        epochs_copy = epochs.copy()

        # Create autoreject object and fit it with the data
        reject = AutoReject(
            consensus=[1.0], n_interpolate=[0], random_state=97, verbose=False
        )
        reject.fit(epochs_copy)
        # find where channels are considered bad, and extract the ones that are bad longer then threshold percentage
        log = reject.get_reject_log(epochs_copy)
        n_epochs = len(epochs)
        n_bads = log.labels.sum(axis=0)
        # Index of bad channels, drop them and evaluate...
        bads_index = np.where(n_bads > n_epochs * 0.5)[0]

        if bads_index.size > 0:
            bads_name_autorej2 = [epochs_copy.ch_names[idx] for idx in bads_index]
            epochs_copy.drop_channels(bads_name_autorej2)
        else:
            bads_name_autorej2 = []

        evaluate_other(epochs_copy, bads_name_autorej2, results[3, :], base_line)

        if len(bads_name_autorej2) > 0:
            stats = EpochStats(epochs_copy.copy())
            np.save(save_folder / str(eye) / "bad_channels" / "light_auto"/ str(my_index), np.array(bads_name_autorej2))
        else:
            stats = EpochStats(epochs.copy())

        stats.calc_stability()
        np.save(save_folder / str(eye) / "accumulate" / "light_auto"/ "peaks" / "abs_dis" / str(my_index), stats.get_peak_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "light_auto"/ "peaks" / "dis" / str(my_index), stats.get_peak_stability().get_mean_stab())
        np.save(save_folder / str(eye) / "accumulate" / "light_auto"/ "quasi" / "abs_dis" / str(my_index), stats.get_quasi_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "light_auto"/ "quasi" / "dis" / str(my_index), stats.get_quasi_stability().get_mean_stab())

        montage_kind = "standard_1020"
        montage = mne.channels.make_standard_montage(montage_kind)
        raw_copy = (
            raw.copy()
            .crop(
                start_times[random_start[eye][my_index]],
                end_times[random_start[eye][my_index]],
            )
            .load_data()
        ).resample(sfreq=201, verbose=False)
        sample_rate = raw_copy.info["sfreq"]
        prep_params = {
            "ref_chs": "eeg",
            "reref_chs": "eeg",
            "line_freqs": np.arange(50, sample_rate / 2, 50),
        }

        prep = PrepPipeline(
            raw_copy, prep_params, montage, matlab_strict=True, random_state=435656
        )
        prep.fit()
        bads_name_prep_mat = prep.interpolated_channels + prep.still_noisy_channels
        evaluate_other(epochs.copy().drop_channels(bads_name_prep_mat), bads_name_prep_mat, results[4, :], base_line)

        if len(bads_name_prep_mat) > 0:
            stats = EpochStats(epochs.copy().drop_channels(bads_name_prep_mat))
            np.save(save_folder / str(eye) / "bad_channels" / "prep_mat"/ str(my_index), np.array(bads_name_prep_mat))
        else:
            stats = EpochStats(epochs.copy())

        stats.calc_stability()
        np.save(save_folder / str(eye) / "accumulate" / "prep_mat"/ "peaks" / "abs_dis" / str(my_index), stats.get_peak_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "prep_mat"/ "peaks" / "dis" / str(my_index), stats.get_peak_stability().get_mean_stab())
        np.save(save_folder / str(eye) / "accumulate" / "prep_mat"/ "quasi" / "abs_dis" / str(my_index), stats.get_quasi_stability().get_mean_abs_stab())
        np.save(save_folder / str(eye) / "accumulate" / "prep_mat"/ "quasi" / "dis" / str(my_index), stats.get_quasi_stability().get_mean_stab())


        np.save(save_folder / str(eye) / "base_line" / f"{my_index}", base_line)
        np.save(save_folder / str(eye) / "results" / f"{my_index}", results)


# Run experiments
if __name__ == "__main__":
    for i in range(0, 201, 16):
        p0 = Process(target=process, args=(i,))
        p1 = Process(target=process, args=(i + 1,))
        p2 = Process(target=process, args=(i + 2,))
        p3 = Process(target=process, args=(i + 3,))
        p4 = Process(target=process, args=(i + 4,))
        p5 = Process(target=process, args=(i + 5,))
        p6 = Process(target=process, args=(i + 6,))
        p7 = Process(target=process, args=(i + 7,))
        p8 = Process(target=process, args=(i + 8,))
        p9 = Process(target=process, args=(i + 9,))
        p10 = Process(target=process, args=(i + 10,))
        p11 = Process(target=process, args=(i + 11,))
        p12 = Process(target=process, args=(i + 12,))
        p13 = Process(target=process, args=(i + 13,))
        p14 = Process(target=process, args=(i + 14,))
        p15 = Process(target=process, args=(i + 15,))

        p0.start()
        p1.start()
        p2.start()
        p3.start()
        p4.start()
        p5.start()
        p6.start()
        p7.start()
        p8.start()
        p9.start()
        p10.start()
        p11.start()
        p12.start()
        p13.start()
        p14.start()
        p15.start()

        p0.join()
        p1.join()
        p2.join()
        p3.join()
        p4.join()
        p5.join()
        p6.join()
        p7.join()
        p8.join()
        p9.join()
        p10.join()
        p11.join()
        p12.join()
        p13.join()
        p14.join()
        p15.join()
