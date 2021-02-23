# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
 xcp_abcd  postprocessing workflows
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. autofunction:: init_xcpabcd_wf

"""

import sys
import os
from copy import deepcopy
from nipype import __version__ as nipype_ver
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from ..__about__ import __version__

from ..utils import collect_data

from  ..workflow import( init_ciftipostprocess_wf, 
            init_boldpostprocess_wf)
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from ..interfaces import SubjectSummary, AboutSummary
from  ..utils import bid_derivative



def init_xcpabcd_wf(layout,
                   lowpass,
                   highpass,
                   fmriprep_dir,
                   omp_nthreads,
                   cifti,
                   task_id,
                   head_radius,
                   params,
                   template,
                   subject_list,
                   smoothing,
                   custom_conf,
                   bids_filters,
                   output_dir,
                   work_dir,
                   scrub,
                   dummytime,
                   fd_thresh,
                   name):
    
    """
    This workflow builds and organizes  execution of  xcp_abcd  pipeline.
    It is also connect the subworkflows under the xcp_abcd
    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes
            xcp_abcd.workflow.base import init_xcpabcd_wf
            wf = init_xcpabcd_wf(
                layout,
                lowpass,
                highpass,
                fmriprep_dir,
                omp_nthreads,
                cifti,
                task_id,
                head_radius,
                params,
                template,
                subject_list,
                smoothing,
                custom_conf,
                bids_filters,
                output_dir,
                work_dir,
                scrub,
                dummytime,
                fd_thresh
            )
    Parameters
    ----------
    lowpass : float
        Low pass filter
    highpass : float
        High pass filter
    layout : BIDSLayout object
        BIDS dataset layout 
    fmriprep_dir : Path
        fmriprep output directory
    omp_nthreads : int
        Maximum number of threads an individual process may use
    cifti : bool
        To postprocessed cifti files instead of nifti
    task_id : str or None
        Task ID of BOLD  series to be selected for postprocess , or ``None`` to postprocess all
    low_mem : bool
        Write uncompressed .nii files in some cases to reduce memory usage
    output_dir : str
        Directory in which to save xcp_abcd output
    fd_thresh
        Criterion for flagging framewise displacement outliers
    run_uuid : str
        Unique identifier for execution instance
    subject_list : list
        List of subject labels
    work_dir : str
        Directory in which to store workflow execution state and temporary files
    head_radius : float 
        radius of the head for FD computation
    params: str
        nuissance regressors to be selected from fmriprep regressors
    smoothing: float
        smooth the derivatives output with kernel size (fwhm)
    custom_conf: str
        path to cusrtom nuissance regressors 
    scrub: bool 
        remove the censored volumes 
    dummytime: float
        the first vols in seconds to be removed before postprocessing
    
    """

    xcpabcd_wf = Workflow(name='xcpabcd_wf')
    xcpabcd_wf.base_dir = work_dir

    for subject_id in subject_list:
        single_bold_wf = init_single_bold_wf(
                            layout=layout,
                            lowpass=lowpass,
                            highpass=highpass,
                            fmriprep_dir=fmriprep_dir,
                            omp_nthreads=omp_nthreads,
                            subject_id=subject_id,
                            cifti=cifti,
                            head_radius=head_radius,
                            params=params,
                            task_id=task_id,
                            template=template,
                            smoothing=smoothing,
                            custom_conf=custom_conf,
                            bids_filters=bids_filters,
                            output_dir=output_dir,
                            scrub=scrub,
                            dummytime=dummytime,
                            fd_thresh=fd_thresh,
                            name="single_bold_" + subject_id + "_wf")

        single_bold_wf.config['execution']['crashdump_dir'] = (
            os.path.join(output_dir, "xcp_abcd", "sub-" + subject_id, 'log')
        )
        for node in single_bold_wf._get_all_nodes():
            node.config = deepcopy(single_bold_wf.config)
        xcpabcd_wf.add_nodes([single_bold_wf])

    return xcpabcd_wf


def init_single_bold_wf(
    layout,
    lowpass,
    highpass,
    fmriprep_dir,
    omp_nthreads,
    subject_id,
    cifti,
    head_radius,
    params,
    scrub,
    dummytime,
    fd_thresh,
    task_id,
    template,
    smoothing,
    custom_conf,
    bids_filters,
    output_dir,
    name
    ):
    """
    This workflow organizes the postprocessing pipeline for a single bold or cifti.
    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes
            from xcp_abcd.workflows.base import init_single_bold_wf
            wf = init_single_bold_wf(
                layout,
                lowpass,
                highpass,
                fmriprep_dir,
                omp_nthreads,
                subject_id,
                cifti,
                head_radius,
                params,
                scrub,
                dummytime,
                fd_thresh,
                task_id,
                template,
                smoothing,
                custom_conf,
                bids_filters,
                output_dir
             )
    Parameters
    ----------
    lowpass : float
        Low pass filter
    highpass : float
        High pass filter
    layout : BIDSLayout object
        BIDS dataset layout 
    fmriprep_dir : Path
        fmriprep output directory
    omp_nthreads : int
        Maximum number of threads an individual process may use
    cifti : bool
        To postprocessed cifti files instead of nifti
    task_id : str or None
        Task ID of BOLD  series to be selected for postprocess , or ``None`` to postprocess all
    low_mem : bool
        Write uncompressed .nii files in some cases to reduce memory usage
    output_dir : str
        Directory in which to save xcp_abcd output
    fd_thresh
        Criterion for flagging framewise displacement outliers
    head_radius : float 
        radius of the head for FD computation
    params: str
        nuissance regressors to be selected from fmriprep regressors
    smoothing: float
        smooth the derivatives output with kernel size (fwhm)
    custom_conf: str
        path to cusrtom nuissance regressors 
    scrub: bool 
        remove the censored volumes 
    dummytime: float
        the first vols in seconds to be removed before postprocessing

    """
    layout,subject_data,regfile = collect_data(bids_dir=fmriprep_dir,participant_label=subject_id, 
                                               task=task_id,bids_validate=False, 
                                               bids_filters=bids_filters,template=template)
    inputnode = pe.Node(niu.IdentityInterface(
        fields=['custom_conf','mni_to_t1w']),
        name='inputnode')
    inputnode.inputs.custom_conf = custom_conf
    inputnode.inputs.mni_to_t1w = regfile[0]
    
    workflow = Workflow(name=name)
    
    workflow.__desc__ = """
#### Postprocessing of fMRIPrep outputs
Results included in this manuscript come from postprocessing offMRIPrep 
outputs [@fmriprep1;@fmriprep2]. The postprocessing was  performed using 
*xcp_abcd* [@mitigating_2018;@satterthwaite_2013;@benchmarkp] which is based 
on *Nipype* {nipype_ver} [@nipype1; @nipype2].

""".format(nipype_ver=nipype_ver)


    workflow.__postdesc__ = """


Many internal operations of *xcp_abcd* use *Nibabel* [@nilearn], *numpy* 
[@harris2020array] and  *scipy* [@2020SciPy-NMeth], mostly within the 
functional post-processing workflow.For more details of the pipeline, 
see  the *xcp_abcd* website (coming).


#### Copyright Waiver
The above boilerplate text was automatically generated by *xcp_abcd*
with the express intention that users should copy and paste this
text into their manuscripts *unchanged*.
It is released under the [CC0]\
(https://creativecommons.org/publicdomain/zero/1.0/) license.

#### References

"""


    summary = pe.Node(SubjectSummary(subject_id=subject_id,bold=subject_data[0]),
                      name='summary', run_without_submitting=True)

    about = pe.Node(AboutSummary(version=__version__,
                                 command=' '.join(sys.argv)),
                    name='about', run_without_submitting=True)

    ds_report_summary = pe.Node(
        DerivativesDataSink(base_directory=output_dir,source_file=subject_data[0][0],desc='summary', datatype="figures"),
                  name='ds_report_summary', run_without_submitting=True)

    

    if cifti:
        ii=0
        for cifti_file in subject_data[1]:
            ii = ii+1
            cifti_postproc_wf = init_ciftipostprocess_wf(cifti_file=cifti_file,
                                                        lowpass=lowpass,
                                                        highpass=highpass,
                                                        smoothing=smoothing,
                                                        head_radius=head_radius,
                                                        params=params,
                                                        custom_conf=custom_conf,
                                                        omp_nthreads=omp_nthreads,
                                                        num_cifti=len(subject_data[1]),
                                                        scrub=scrub,
                                                        dummytime=dummytime,
                                                        fd_thresh=fd_thresh,
                                                        layout=layout,
                                                        output_dir=output_dir,
                                                        name='cifti_postprocess_'+ str(ii) + '_wf')
            ds_report_about = pe.Node(
             DerivativesDataSink(base_directory=output_dir, source_file=cifti_file, desc='about', datatype="figures",),
              name='ds_report_about', run_without_submitting=True)
            workflow.connect([
                  (inputnode,cifti_postproc_wf,[('custom_conf','inputnode.custom_conf')]),
            
            ])

            
    else:
        ii = 0
        for bold_file in subject_data[0]:
            ii = ii+1
            mni_to_t1w = regfile[0]
            inputnode.inputs.mni_to_t1w = mni_to_t1w
            bold_postproc_wf = init_boldpostprocess_wf(bold_file=bold_file,
                                                       lowpass=lowpass,
                                                       highpass=highpass,
                                                       smoothing=smoothing,
                                                       head_radius=head_radius,
                                                       params=params,
                                                       omp_nthreads=omp_nthreads,
                                                       template='MNI152NLin2009cAsym',
                                                       num_bold=len(subject_data[0]),
                                                       custom_conf=custom_conf,
                                                       layout=layout,
                                                       scrub=scrub,
                                                       dummytime=dummytime,
                                                       fd_thresh=fd_thresh,
                                                       output_dir=output_dir,
                                                       name='bold_postprocess_'+ str(ii) + '_wf')
            ds_report_about = pe.Node(
             DerivativesDataSink(base_directory=output_dir, source_file=bold_file, desc='about', datatype="figures",),
              name='ds_report_about', run_without_submitting=True)
            workflow.connect([
                  (inputnode,bold_postproc_wf,[ ('mni_to_t1w','inputnode.mni_to_t1w')]),
            ])
    workflow.connect([ 
        (summary,ds_report_summary,[('out_report','in_file')]),
        (about, ds_report_about, [('out_report', 'in_file')]),
         
       ])
    for node in workflow.list_node_names():
        if node.split('.')[-1].startswith('ds_'):
            workflow.get_node(node).interface.out_path_base = 'xcp_abcd'

    return workflow


def _prefix(subid):
    if subid.startswith('sub-'):
        return subid
    return '-'.join(('sub', subid))


def _pop(inlist):
    if isinstance(inlist, (list, tuple)):
        return inlist[0]
    return inlist

class DerivativesDataSink(bid_derivative):
    out_path_base = 'xcp_abcd'